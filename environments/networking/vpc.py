from pulumi import ComponentResource, ResourceOptions, InvokeOptions
import pulumi_aws as aws

from leviathan.configuration import cidrs


class Vpc(ComponentResource):
    def __init__(self, name: str, opts) -> None:
        # By calling super(), we ensure any instantiation of this class inherits from the ComponentResource class so we don't have to declare all the same things all over again.
        super().__init__(
            "pkg:leviathan:environments:networking:vpc", name, None, opts=opts
        )
        # This definition ensures the new component resource acts like anything else in the Pulumi ecosystem when being called in code.

        cidr_prefix = cidrs.CIDR_PREFIX_NETWORKING

        main_vpc = aws.ec2.Vpc(
            name,
            cidr_block=f"{cidr_prefix}.0.0/16",
            tags={
                "Name": name,
            },
            opts=opts,
        )

        availability_zones = aws.get_availability_zones(
            opts=InvokeOptions(provider=opts.providers["aws"])
        ).names

        private_subnets = []
        private_subnet_suffixes = ["30.0/24", "20.0/24", "10.0/24"]

        public_subnets = []
        public_subnet_suffixes = ["60.0/24", "50.0/24", "40.0/24"]

        for az in availability_zones:
            private_subnets.append(
                aws.ec2.Subnet(
                    f"{az}-private-subnet",
                    assign_ipv6_address_on_creation=False,
                    availability_zone=az,
                    cidr_block=f"{cidr_prefix}.{private_subnet_suffixes.pop()}",
                    map_public_ip_on_launch=False,
                    vpc_id=main_vpc.id,
                    tags={
                        'Name': '{az}-private-subnet',
                        'Type': 'private',
                    },
                    opts=opts,
                )
            )

            public_subnets.append(
                aws.ec2.Subnet(
                    f"{az}-public-subnet",
                    assign_ipv6_address_on_creation=False,
                    availability_zone=availability_zones[0],
                    cidr_block=f"{cidr_prefix}.{public_subnet_suffixes.pop()}",
                    map_public_ip_on_launch=False,
                    vpc_id=main_vpc.id,
                    tags={
                        'Name': '{az}-public-subnet',
                        'Type': 'public',
                    },
                    opts=opts,
                )
            )

        self.register_outputs({})
