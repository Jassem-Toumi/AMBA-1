
# AMBA stands for AWS Migration Between Accounts
This project is an open-source web-based application designed to facilitate the migration of AWS EC2 instances between AWS accounts. The tool provides a user-friendly interface for non-technical individuals to perform resource migrations with minimal effort.

# Key Features
- Simple Setup: Easily configure source and destination AWS accounts.
- Instance Selection: Scan and select instances from your source account.
- Seamless Migration: Migrate instances with minimal effort.

# Steps to Use
1. Scan Resources in Source Account

Enter Source AWS Credentials:
AWS Access Key ID
AWS Secret Access Key
Region Name
List Instances: Click the "List Instances" button to scan and display instances in your source account.
Select Instances: Choose the instances you wish to migrate by checking the boxes next to their IDs.

2. Configure Destination Account

Enter Destination AWS Credentials:
AWS Account ID
AWS Access Key ID
AWS Secret Access Key
Region Name
Migrate Resources: Click the "Migrate Resources" button. A modal will prompt you to select or create necessary VPCs, Subnets, and Security Groups in the destination account.

3. Complete Migration

Select VPC: Choose an existing VPC or create a new one.
Select Subnet: Choose an existing Subnet or create a new one.
Select Security Group: Choose an existing Security Group or create a new one.
Confirm and Migrate: Once all selections are made, confirm to start the migration process. A loading animation will indicate progress.
Finish: After successful migration, a confirmation message will be displayed.


To run the frontend application:
- npm run dev

To run backend:
- uvicorn main:app --reload

