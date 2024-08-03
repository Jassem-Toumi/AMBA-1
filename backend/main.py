from typing import Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import boto3
import datetime
import time
from fastapi.middleware.cors import CORSMiddleware
import os


app = FastAPI()


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    # allow all origins
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


class Credentials(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key: str
    region_name: str
    vpc_id: str  # Add VPC ID here


class MigrationRequest(BaseModel):
    source_aws_access_key_id: str
    source_aws_secret_access_key: str
    source_region_name: str
    dest_account_id: str
    dest_aws_access_key_id: str
    dest_aws_secret_access_key: str
    dest_region_name: str
    instance_id: str
    selected_vpc_id: str
    selected_subnet_id: str
    selected_security_group_id: str


def create_ec2_client(aws_access_key_id, aws_secret_access_key, region_name):
    return boto3.client(
        'ec2',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name
    )


# establish a connection to the source and destination ec2 clients
def establish_connection(request):
    source_ec2 = create_ec2_client(
        request.source_aws_access_key_id,
        request.source_aws_secret_access_key,
        request.source_region_name
    )
    dest_ec2 = create_ec2_client(
        request.dest_aws_access_key_id,
        request.dest_aws_secret_access_key,
        request.dest_region_name
    )
    return source_ec2, dest_ec2


@app.post("/list-instances")
def list_instances(credentials: Credentials):
    ec2 = boto3.client(
        'ec2',
        aws_access_key_id=credentials.aws_access_key_id,
        aws_secret_access_key=credentials.aws_secret_access_key,
        region_name=credentials.region_name
    )
    instances = ec2.describe_instances()
    instance_ids = [instance['InstanceId'] for reservation in instances['Reservations']
                    for instance in reservation['Instances']]
    return {"instances": instance_ids}


# list vpcs: /list-vpcs
@app.post("/list-vpcs")
def list_vpcs(credentials: Credentials):
    ec2 = create_ec2_client(credentials.aws_access_key_id,
                            credentials.aws_secret_access_key, credentials.region_name)
    vpcs = ec2.describe_vpcs()
    vpc_ids = [vpc['VpcId'] for vpc in vpcs['Vpcs']]
    return {"vpcs": vpc_ids}

# list subnets: /list-subnets
# only list subnets that are associated with the selected VPC


@app.post("/list-subnets")
def list_subnets(request: Credentials):
    ec2 = create_ec2_client(request.aws_access_key_id,
                            request.aws_secret_access_key, request.region_name)
    subnets = ec2.describe_subnets(Filters=[
        {'Name': 'vpc-id', 'Values': [request.vpc_id]}
    ])
    subnet_ids = [subnet['SubnetId'] for subnet in subnets['Subnets']]
    return {"subnets": subnet_ids}


# create a subnet
@app.post("/create-subnet")
def create_subnet(self, instance, dest_vpc_id):
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


# list security groups: /list-security-groups
# only list security groups that are associated with the selected VPC2
@app.post("/list-security-groups")
def list_security_groups(request: Credentials):
    print("request from security group: ", request)
    ec2 = create_ec2_client(request.aws_access_key_id,
                            request.aws_secret_access_key, request.region_name)
    security_groups = ec2.describe_security_groups(Filters=[
        {'Name': 'vpc-id', 'Values': [request.vpc_id]}
    ])
    security_group_ids = [sg['GroupId']
                          for sg in security_groups['SecurityGroups']]
    return {"security_groups": security_group_ids}


# create a security group: /create-security-group
@app.post("/create-security-group")
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


# list key pairs: /list-key-pairs
@app.post("/list-key-pairs")
def list_key_pairs(credentials: Credentials):
    ec2 = create_ec2_client(
        credentials.aws_access_key_id, credentials.aws_secret_access_key, credentials.region_name
    )
    key_pairs = ec2.describe_key_pairs()
    key_pair_names = [key_pair['KeyName']
                      for key_pair in key_pairs['KeyPairs']]
    return {"key_pairs": key_pair_names}


'''
Migrations Process:
we gonna pass the following parameters:
- source_aws_access_key_id
- source_aws_secret_access_key
- source_region_name
- dest_aws_access_key_id
- dest_aws_secret_access_key
- dest_region_name
- instance_id
- selected vpc id or "new" to create a new vpc
- selected subnet id or "new" to create a new subnet
- selected security group id or "new" to create a new security group
- for the key pair, we will auto-select an existing one otherwise create a new one

Meanwhile we need to do the following:
-  Create snapshots of the instance's volumes (we have to create a wait_for_snapshot function)
-  Share and copy snapshots to the destination account (we have to create a wait_for_snapshot_copy function)
-  Create an AMI from the copied snapshots

Steps:
1. Get the instance details
2. Get the VPC ID (Or create a new one if needed)
3. Get the subnet ID (Or create a new one if needed)
4. Get the security group IDs (Or create a new one if needed)
5. Create Snapshot of the instance's volumes
6. Share and copy snapshots to the destination account
7. Create an AMI from the copied snapshots
8. get the key pair name (Or create a new one if needed)
9. Launch the instance
10. Return the instance ID
'''

# migrate an instance following the steps above


@app.post("/migrate-instance")
def migrate_instance(request: MigrationRequest):
    # Establish connections to the source and destination EC2 clients
    source_ec2, dest_ec2 = establish_connection(request)

    # create a session for the destination ec2 resources
    dest_ec2_resource = boto3.resource(
        'ec2',
        aws_access_key_id=request.dest_aws_access_key_id,
        aws_secret_access_key=request.dest_aws_secret_access_key,
        region_name=request.dest_region_name
    )

    # describe the selected instance
    instance = source_ec2.describe_instances(
        InstanceIds=[request.instance_id])['Reservations'][0]['Instances'][0]

    # Get the VPC ID (Or create a new one if needed)
    if request.selected_vpc_id == 'new':
        vpc_id = create_vpc(dest_ec2)
    else:
        vpc_id = request.selected_vpc_id

    print("VPC ID: ", vpc_id)

    # Get the subnet ID (Or create a new one if needed)
    if request.selected_subnet_id == 'new':
        subnet_id = create_subnet(instance, vpc_id)
    else:
        subnet_id = request.selected_subnet_id

    print("Subnet ID: ", subnet_id)

    # Get the security group IDs (Or create a new one if needed)
    if request.selected_security_group_id == 'new':
        security_group_ids = create_security_group(instance, vpc_id)
    else:
        security_group_ids = [request.selected_security_group_id]

    print("Security Group IDs: ", security_group_ids)

    # Create Snapshot of the instance's volumes
    snapshot_ids = create_instance_snapshots(instance, source_ec2)

    # Wait for the snapshots to be completed
    wait_for_snapshots(snapshot_ids, source_ec2)

    # Share and copy snapshots to the destination account
    snapshot_copy_ids = share_and_copy_snapshots(
        snapshot_ids, source_ec2,  request.dest_account_id, dest_ec2)

    # Wait for the copied snapshots to be completed
    wait_for_copied_snapshots(snapshot_copy_ids, dest_ec2)

    # Create an AMI from the copied snapshots
    ami_id = create_ami(instance, snapshot_copy_ids, dest_ec2)

    # create a new key pair
    key_name = f"key-{instance['InstanceId']}"
    key_pair_name = create_key_pair(dest_ec2, key_name)

    # Launch the instance
    instance_id = launch_instance(
        ami_id, subnet_id, security_group_ids, key_pair_name, instance, dest_ec2_resource)

    return {"instance_id": instance_id}


# create a new VPC
def create_vpc(dest_ec2):
    response = dest_ec2.create_vpc(
        CidrBlock='10.0.0.0/16'
    )
    vpc_id = response['Vpc']['VpcId']
    dest_ec2.modify_vpc_attribute(
        VpcId=vpc_id,
        EnableDnsSupport={'Value': True}
    )
    dest_ec2.modify_vpc_attribute(
        VpcId=vpc_id,
        EnableDnsHostnames={'Value': True}
    )
    return vpc_id

# create snapshots of the instance's volumes


def create_instance_snapshots(instance, source_ec2):
    snapshots = []
    for volume in instance['BlockDeviceMappings']:
        if 'Ebs' in volume:
            volume_id = volume['Ebs']['VolumeId']
            snapshot = source_ec2.create_snapshot(
                VolumeId=volume_id, Description="Snapshot for migration")
            snapshots.append(snapshot['SnapshotId'])
    return snapshots


#  wait for snapshots to be completed
def wait_for_snapshots(snapshots, source_ec2):
    for snapshot_id in snapshots:
        while True:
            response = source_ec2.describe_snapshots(
                SnapshotIds=[snapshot_id])
            snapshot_status = response['Snapshots'][0]['State']
            if snapshot_status == 'completed':
                break
            time.sleep(5)

# share and copy snapshots to the destination account


def share_and_copy_snapshots(snapshot_ids, source_ec2, dest_account_id, dest_ec2):
    for snapshot_id in snapshot_ids:
        source_ec2.modify_snapshot_attribute(
            SnapshotId=snapshot_id,
            Attribute='createVolumePermission',
            OperationType='add',
            UserIds=[dest_account_id]
        )
    copied_snapshots = []
    for snapshot_id in snapshot_ids:
        copied_snapshot = dest_ec2.copy_snapshot(
            SourceRegion=source_ec2.meta.region_name,
            SourceSnapshotId=snapshot_id,
            Description='Copied snapshot for migration'
        )
        copied_snapshots.append(copied_snapshot['SnapshotId'])
    return copied_snapshots


# wait for copied snapshots to be completed
def wait_for_copied_snapshots(snapshots, dest_ec2):
    for snapshot_id in snapshots:
        while True:
            response = dest_ec2.describe_snapshots(
                SnapshotIds=[snapshot_id])
            snapshot_status = response['Snapshots'][0]['State']
            if snapshot_status == 'completed':
                break
            time.sleep(5)

# create an AMI from the copied snapshots


def create_ami(instance, snapshots, dest_ec2):
    block_device_mappings = []

    # Ensure the instance details are correctly passed
    for volume, snapshot_id in zip(instance['BlockDeviceMappings'], snapshots):
        if 'Ebs' in volume:
            block_device_mappings.append({
                'DeviceName': volume['DeviceName'],
                'Ebs': {
                    'SnapshotId': snapshot_id
                }
            })

    # Construct the AMI name
    ami_name = f"AMI-from-{instance['InstanceId']
                           }-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Register the image in the destination account
    ami = dest_ec2.register_image(
        Name=ami_name,
        BlockDeviceMappings=block_device_mappings,
        RootDeviceName=instance['RootDeviceName'],
        VirtualizationType='hvm'
    )

    # Return the AMI ID
    return ami['ImageId']


# create or get a new key pair


def create_key_pair(dest_ec2, key_name):
    # Check if the key pair already exists
    try:
        dest_ec2.describe_key_pairs(KeyNames=[key_name])
        print(f"Key pair {key_name} already exists.")
    except dest_ec2.exceptions.ClientError as e:
        if 'InvalidKeyPair.NotFound' in str(e):
            # Key pair does not exist, so create it
            key_pair = dest_ec2.create_key_pair(KeyName=key_name)
            private_key = key_pair['KeyMaterial']
            private_key_file = f"{key_name}.pem"
            with open(private_key_file, 'w') as file:
                file.write(private_key)
            # Set permissions for the private key file
            os.chmod(private_key_file, 0o400)
            print(f"Key pair {key_name} created and saved to {
                  private_key_file}.")
        else:
            raise e
    return key_name


#  launch the instance
def launch_instance(ami_id, subnet_id, security_group_ids, key_name, source_ec2, dest_ec2_resource):
    instance_type = source_ec2['InstanceType']
    unique_instance_name = f"Instance-from-AMI-{
        datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

    try:
        # Launch the instance
        new_instance = dest_ec2_resource.create_instances(
            ImageId=ami_id,
            MinCount=1,
            MaxCount=1,
            InstanceType=instance_type,
            KeyName=key_name,
            NetworkInterfaces=[{
                'SubnetId': subnet_id,
                'DeviceIndex': 0,
                'AssociatePublicIpAddress': True,
                'Groups': security_group_ids  # Pass the security group IDs directly
            }],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': unique_instance_name}
                ]
            }]
        )
        return new_instance[0].id
    except Exception as e:
        print(f"Error launching instance: {e}")
        raise


# TEST


@app.get("/")
async def root():
    return {"message": "Hello World"}
