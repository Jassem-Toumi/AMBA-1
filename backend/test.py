import boto3
import time
import os
import datetime


class EmigrateEC2Instances:
    def __init__(self, source_credentials, dest_credentials, region_name):
        self.source_session = boto3.Session(
            aws_access_key_id=source_credentials['aws_access_key_id'],
            aws_secret_access_key=source_credentials['aws_secret_access_key'],
            region_name=region_name
        )
        self.dest_session = boto3.Session(
            aws_access_key_id=dest_credentials['aws_access_key_id'],
            aws_secret_access_key=dest_credentials['aws_secret_access_key'],
            region_name=region_name
        )

        self.source_ec2 = self.source_session.client('ec2')
        self.dest_ec2 = self.dest_session.client('ec2')
        self.dest_ec2_resource = self.dest_session.resource('ec2')

    def describe_instance(self, instance_id):
        response = self.source_ec2.describe_instances(
            InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        return instance

    def get_existing_vpcs(self):
        response = self.dest_ec2.describe_vpcs()
        return response.get('Vpcs', [])

    def create_vpc(self):
        response = self.dest_ec2.create_vpc(
            CidrBlock='10.0.0.0/16'
        )
        vpc_id = response['Vpc']['VpcId']
        self.dest_ec2.modify_vpc_attribute(
            VpcId=vpc_id,
            EnableDnsSupport={'Value': True}
        )
        self.dest_ec2.modify_vpc_attribute(
            VpcId=vpc_id,
            EnableDnsHostnames={'Value': True}
        )
        return vpc_id

    def select_vpc(self):
        vpcs = self.get_existing_vpcs()
        print("Existing VPCs:")
        for i, vpc in enumerate(vpcs):
            print(f"{i+1}. VPC ID: {vpc['VpcId']}, CIDR: {vpc['CidrBlock']}")
        choice = input(
            "Select a VPC by number, or enter 'new' to create a new VPC: ")
        if choice.lower() == 'new':
            return self.create_vpc()
        else:
            return vpcs[int(choice) - 1]['VpcId']

    def create_subnets(self, instance, dest_vpc_id):
        # Get existing subnets to avoid conflicts
        existing_subnets = self.dest_ec2.describe_subnets(Filters=[
            {'Name': 'vpc-id', 'Values': [dest_vpc_id]}
        ])
        existing_cidrs = [subnet['CidrBlock']
                          for subnet in existing_subnets['Subnets']]

        # Define new CIDR blocks that are unlikely to conflict
        new_cidr_block = '10.0.1.0/24'  # Change this if needed

        # Ensure the new CIDR block does not overlap with existing ones
        while new_cidr_block in existing_cidrs:
            new_cidr_block = self.get_next_available_cidr_block(new_cidr_block)

        # Create the new subnet
        new_subnet = self.dest_ec2.create_subnet(
            CidrBlock=new_cidr_block,
            VpcId=dest_vpc_id,
            AvailabilityZone=instance['Placement']['AvailabilityZone']
        )
        subnet_id = new_subnet['Subnet']['SubnetId']

        # Create and attach an internet gateway if not already existing
        igw_response = self.dest_ec2.describe_internet_gateways(Filters=[
            {'Name': 'attachment.vpc-id', 'Values': [dest_vpc_id]}
        ])
        if not igw_response['InternetGateways']:
            igw = self.dest_ec2.create_internet_gateway()
            self.dest_ec2.attach_internet_gateway(
                InternetGatewayId=igw['InternetGateway']['InternetGatewayId'],
                VpcId=dest_vpc_id
            )
            igw_id = igw['InternetGateway']['InternetGatewayId']
        else:
            igw_id = igw_response['InternetGateways'][0]['InternetGatewayId']

        # Create a route table
        route_table_response = self.dest_ec2.create_route_table(
            VpcId=dest_vpc_id)
        route_table_id = route_table_response['RouteTable']['RouteTableId']

        # Create a route in the route table
        self.dest_ec2.create_route(
            RouteTableId=route_table_id,
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=igw_id
        )

        # Associate the route table with the subnet
        self.dest_ec2.associate_route_table(
            SubnetId=subnet_id,
            RouteTableId=route_table_id
        )

        # Modify the subnet attribute to enable public IP assignment
        self.dest_ec2.modify_subnet_attribute(
            SubnetId=subnet_id,
            MapPublicIpOnLaunch={'Value': True}
        )

        return subnet_id

    def select_subnet(self, vpc_id):
        response = self.dest_ec2.describe_subnets(
            Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
        )
        subnets = response.get('Subnets', [])
        print("Existing Subnets:")
        for i, subnet in enumerate(subnets):
            print(
                f"{i+1}. Subnet ID: {subnet['SubnetId']}, CIDR: {subnet['CidrBlock']}")
        choice = input(
            "Select a subnet by number, or enter 'new' to create a new subnet: ")
        if choice.lower() == 'new':
            return self.create_subnet(vpc_id)
        else:
            return subnets[int(choice) - 1]['SubnetId']

    def create_security_group(self, instance, dest_vpc_id):
        security_groups = instance['SecurityGroups']
        created_security_groups = []
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        for sg in security_groups:
            sg_info = self.source_ec2.describe_security_groups(
                GroupIds=[sg['GroupId']])['SecurityGroups'][0]
            unique_sg_name = f"migrated-{sg_info['GroupName']}-{timestamp}"
            new_sg = self.dest_ec2.create_security_group(
                GroupName=unique_sg_name,
                Description=sg_info['Description'],
                VpcId=dest_vpc_id
            )
            created_security_groups.append(new_sg['GroupId'])

            for perm in sg_info['IpPermissions']:
                self.dest_ec2.authorize_security_group_ingress(
                    GroupId=new_sg['GroupId'],
                    IpPermissions=[perm]
                )

            # Add EC2 Instance Connect IP addresses
            ec2_instance_connect_ips = '3.16.146.0/29'
            self.dest_ec2.authorize_security_group_ingress(
                GroupId=new_sg['GroupId'],
                IpProtocol='tcp',
                FromPort=22,
                ToPort=22,
                CidrIp=ec2_instance_connect_ips
            )

        return created_security_groups

    def select_security_group(self, vpc_id, instance):
        response = self.dest_ec2.describe_security_groups(
            Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
        )
        sgs = response.get('SecurityGroups', [])
        print("Existing Security Groups:")
        for i, sg in enumerate(sgs):
            print(f"{i+1}. SG ID: {sg['GroupId']}, Name: {sg['GroupName']}")
        choice = input(
            "Select a security group by number, or enter 'new' to create a new security group: ")
        if choice.lower() == 'new':
            return self.create_security_group(vpc_id, instance)
        else:
            return sgs[int(choice) - 1]['GroupId']

    def create_snapshots(self, instance):
        snapshots = []
        for volume in instance['BlockDeviceMappings']:
            if 'Ebs' in volume:
                volume_id = volume['Ebs']['VolumeId']
                snapshot = self.source_ec2.create_snapshot(
                    VolumeId=volume_id, Description="Snapshot for migration")
                snapshots.append(snapshot['SnapshotId'])
        return snapshots

    def wait_for_snapshots(self, snapshots):
        for snapshot_id in snapshots:
            while True:
                response = self.source_ec2.describe_snapshots(
                    SnapshotIds=[snapshot_id])
                snapshot_status = response['Snapshots'][0]['State']
                if snapshot_status == 'completed':
                    break
                time.sleep(5)

    def share_snapshots(self, snapshots, dest_account_id):
        for snapshot_id in snapshots:
            self.source_ec2.modify_snapshot_attribute(
                SnapshotId=snapshot_id,
                Attribute='createVolumePermission',
                OperationType='add',
                UserIds=[dest_account_id]
            )
        
    def copy_snapshots(self, snapshots):
        copied_snapshots = []
        for snapshot_id in snapshots:
            copied_snapshot = self.dest_ec2.copy_snapshot(
                SourceRegion=self.source_ec2.meta.region_name,
                SourceSnapshotId=snapshot_id,
                Description='Copied snapshot for migration'
            )
            copied_snapshots.append(copied_snapshot['SnapshotId'])
        return copied_snapshots

    def wait_for_copied_snapshots(self, snapshots):
        for snapshot_id in snapshots:
            while True:
                response = self.dest_ec2.describe_snapshots(
                    SnapshotIds=[snapshot_id])
                snapshot_status = response['Snapshots'][0]['State']
                if snapshot_status == 'completed':
                    break
                time.sleep(5)
            
    

    def create_ami(self, instance, snapshots):
        block_device_mappings = []
        for volume, snapshot_id in zip(instance['BlockDeviceMappings'], snapshots):
            if 'Ebs' in volume:
                block_device_mappings.append({
                    'DeviceName': volume['DeviceName'],
                    'Ebs': {
                        'SnapshotId': snapshot_id
                    }
                })

        ami_name = f"AMI-from-{instance['InstanceId']
                               }-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        ami = self.dest_ec2.register_image(
            Name=ami_name,
            BlockDeviceMappings=block_device_mappings,
            RootDeviceName=instance['RootDeviceName'],
            VirtualizationType='hvm'
        )
        return ami['ImageId']

    def create_key_pair(self, key_name):
        # Check if the key pair already exists
        try:
            self.dest_ec2.describe_key_pairs(KeyNames=[key_name])
            print(f"Key pair {key_name} already exists.")
        except self.dest_ec2.exceptions.ClientError as e:
            if 'InvalidKeyPair.NotFound' in str(e):
                # Key pair does not exist, so create it
                key_pair = self.dest_ec2.create_key_pair(KeyName=key_name)
                private_key = key_pair['KeyMaterial']
                with open(f"{key_name}.pem", 'w') as file:
                    file.write(private_key)
                os.chmod(f"{key_name}.pem", 0o400)
            else:
                raise e

    def launch_instance(self, ami_id, instance, security_group_ids, subnet_id, key_name):
        instance_type = instance['InstanceType']
        unique_instance_name = f"Instance-from-AMI-{
            datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        new_instance = self.dest_ec2_resource.create_instances(
            ImageId=ami_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,
            KeyName=key_name,
            NetworkInterfaces=[{
                'SubnetId': subnet_id,
                'DeviceIndex': 0,
                'AssociatePublicIpAddress': True,
                'Groups': [security_group_ids]
            }],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': unique_instance_name}
                ]
            }]
        )
        return new_instance[0].id

    def emigrate_instance(self, instance_id, dest_account_id):
        instance = self.describe_instance(instance_id)

        # Select or create a VPC
        dest_vpc_id = self.select_vpc()

        # Select or create a subnet
        subnet_id = self.select_subnet(dest_vpc_id)

        # Select or create a security group
        security_group_id = self.select_security_group(dest_vpc_id, instance)

        # Create snapshots of the instance's volumes
        snapshots = self.create_snapshots(instance)
        self.wait_for_snapshots(snapshots)

        # Share and copy snapshots to the destination account
        self.share_snapshots(snapshots, dest_account_id)
        copied_snapshots = self.copy_snapshots(snapshots)
        self.wait_for_copied_snapshots(copied_snapshots)

        # Create an AMI from the copied snapshots
        ami_id = self.create_ami(instance, copied_snapshots)

        # Create a new key pair
        key_name = f"key-{instance_id}"
        self.create_key_pair(key_name)

        # Launch the new instance from the AMI
        new_instance_id = self.launch_instance(
            ami_id, instance, security_group_id, subnet_id, key_name)
        return new_instance_id


def main():
    source_credentials = {
        'aws_access_key_id': 'Write your access key here',
        'aws_secret_access_key': 'Write your secret key here'
    }
    dest_credentials = {
        'aws_access_key_id': 'Write your access key here',
        'aws_secret_access_key': 'Write your secret key here'
    }
    region_name = 'Write your region here'

    migrator = EmigrateEC2Instances(
        source_credentials, dest_credentials, region_name)

    # List EC2 instances in source account
    instances = migrator.source_ec2.describe_instances()
    instance_ids = []
    print("Available instances in source account:")
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            print(f"ID: {instance['InstanceId']}, Name: {
                  instance.get('Tags', [{'Value': 'No Name'}])[0]['Value']}")
            instance_ids.append(instance['InstanceId'])

    # Ask user to select instances to migrate
    selected_instance_ids = []
    while True:
        selected_id = input(
            "Enter the ID of the EC2 instance to migrate (or 'done' to finish): ")
        if selected_id.lower() == 'done':
            break
        if selected_id in instance_ids:
            selected_instance_ids.append(selected_id)
        else:
            print("Invalid ID. Please try again.")

    dest_account_id = input("Enter the destination AWS account ID: ")

    for instance_id in selected_instance_ids:
        new_instance_id = migrator.emigrate_instance(
            instance_id, dest_account_id)
        print(f"Successfully migrated instance {
              instance_id} to new instance {new_instance_id}")


if __name__ == "__main__":
    main()



