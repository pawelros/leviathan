from pulumi import ComponentResource, ResourceOptions, InvokeOptions
import pulumi_aws as aws
import pulumi
import json


class Vpc(ComponentResource):
    private_subnets = []
    private_subnet_suffixes = ["30.0/24", "20.0/24", "10.0/24"]

    public_subnets = []
    public_subnet_suffixes = ["60.0/24", "50.0/24", "40.0/24"]

    def __init__(
        self, name: str, cidr_prefix: str, opts, is_public: bool = False
    ) -> None:
        # By calling super(), we ensure any instantiation of this class inherits from the ComponentResource class so we don't have to declare all the same things all over again.
        super().__init__(
            "pkg:leviathan:environments:networking:vpc", name, None, opts=opts
        )
        # This definition ensures the new component resource acts like anything else in the Pulumi ecosystem when being called in code.
        child_opts = pulumi.ResourceOptions(parent=self, providers=opts.providers)
        self.name = name
        self.cidr_block = f"{cidr_prefix}.0.0/16"

        main_vpc = aws.ec2.Vpc(
            name,
            cidr_block=self.cidr_block,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            tags={
                "Name": name,
            },
            opts=child_opts,
        )

        self.id = main_vpc.id

        child_opts = pulumi.ResourceOptions(parent=main_vpc, providers=opts.providers)

        self._add_subnets(main_vpc, cidr_prefix, is_public, child_opts)
        self._add_vpc_flow_logs(main_vpc, name, child_opts)

        vpc_data = {
            "vpc": main_vpc.id,
            "cidr_block": self.cidr_block,
            "public_cidrs": [ps.cidr_block for ps in self.public_subnets],
            "private_cidrs": [ps.cidr_block for ps in self.private_subnets],
            "public_subnets": [ps.id for ps in self.public_subnets],
            "private_subnets": [ps.id for ps in self.private_subnets],
        }

        pulumi.export("vpc_info", vpc_data)

        self.register_outputs({})

    def _add_subnets(
        self, main_vpc: aws.ec2.Vpc, cidr_prefix: str, is_public: bool, opts
    ):
        availability_zones = aws.get_availability_zones(
            opts=InvokeOptions(provider=opts.providers["aws"])
        ).names

        for az in availability_zones:
            self.private_subnets.append(
                aws.ec2.Subnet(
                    f"{self.name}-{az}-private-subnet",
                    assign_ipv6_address_on_creation=False,
                    availability_zone=az,
                    cidr_block=f"{cidr_prefix}.{self.private_subnet_suffixes.pop()}",
                    map_public_ip_on_launch=False,
                    vpc_id=main_vpc.id,
                    tags={
                        "Name": f"{az}-private-subnet",
                        "Type": "private",
                    },
                    opts=opts,
                )
            )

            if is_public:
                self.public_subnets.append(
                    aws.ec2.Subnet(
                        f"{self.name}-{az}-public-subnet",
                        assign_ipv6_address_on_creation=False,
                        availability_zone=az,
                        cidr_block=f"{cidr_prefix}.{self.public_subnet_suffixes.pop()}",
                        map_public_ip_on_launch=False,
                        vpc_id=main_vpc.id,
                        tags={
                            "Name": f"{az}-public-subnet",
                            "Type": "public",
                        },
                        opts=opts,
                    )
                )

    def _add_vpc_flow_logs(self, main_vpc: aws.ec2.Vpc, vpc_name: str, opts):
        # TODO: Flow logs should actually be centralized in networking account
        vpc_flowlog_role = aws.iam.Role(
            f"{vpc_name}-vpc-flowlog-role",
            assume_role_policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "",
                            "Effect": "Allow",
                            "Principal": {"Service": "vpc-flow-logs.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                }
            ),
            opts=opts,
        )

        aws.iam.RolePolicy(
            f"{vpc_name}-vpc-flowlog-role-policy",
            role=vpc_flowlog_role.id,
            policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": [
                                "logs:DescribeLogGroups",
                                "logs:DescribeLogStreams",
                                "logs:PutLogEvents",
                            ],
                            "Effect": "Allow",
                            "Resource": "*",
                        }
                    ],
                }
            ),
            opts=pulumi.ResourceOptions(
                parent=vpc_flowlog_role, providers=opts.providers
            ),
        )

        bucket = aws.s3.Bucket(
            f"{vpc_name}-vpc-flowlog-bucket",
            acl="private",
            tags={
                "Name": f"{vpc_name}-vpc-flowlog",
            },
            opts=opts,
        )

        return aws.ec2.FlowLog(
            f"{vpc_name}-vpc-flowlog",
            log_destination=pulumi.Output.concat(bucket.arn, "/", main_vpc.id),
            log_destination_type="s3",
            traffic_type="ALL",
            vpc_id=main_vpc.id,
            destination_options=aws.ec2.FlowLogDestinationOptionsArgs(
                file_format="plain-text",
                per_hour_partition=True,
            ),
            opts=pulumi.ResourceOptions(parent=main_vpc, providers=opts.providers),
        )
