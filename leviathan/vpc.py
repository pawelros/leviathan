from pulumi import ComponentResource, ResourceOptions, InvokeOptions
import pulumi_aws as aws
import pulumi


class Vpc(ComponentResource):
    def __init__(self, name: str, cidr_prefix: str, opts, is_public: bool = False) -> None:
        # By calling super(), we ensure any instantiation of this class inherits from the ComponentResource class so we don't have to declare all the same things all over again.
        super().__init__(
            "pkg:leviathan:environments:networking:vpc", name, None, opts=opts
        )
        # This definition ensures the new component resource acts like anything else in the Pulumi ecosystem when being called in code.

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
                        'Name': f'{az}-private-subnet',
                        'Type': 'private',
                    },
                    opts=opts,
                )
            )

            if is_public:
                public_subnets.append(
                    aws.ec2.Subnet(
                        f"{az}-public-subnet",
                        assign_ipv6_address_on_creation=False,
                        availability_zone=az,
                        cidr_block=f"{cidr_prefix}.{public_subnet_suffixes.pop()}",
                        map_public_ip_on_launch=False,
                        vpc_id=main_vpc.id,
                        tags={
                            'Name': f'{az}-public-subnet',
                            'Type': 'public',
                        },
                        opts=opts,
                    )
                )

        vpc_data = {
            'vpc': main_vpc.id,
            'public_cidrs': [ps.cidr_block for ps in public_subnets],
            'private_cidrs': [ps.cidr_block for ps in private_subnets],
            'public_subnets': [ps.id for ps in public_subnets],
            'private_subnets': [ps.id for ps in private_subnets],
        }

        pulumi.export('vpc_info', vpc_data)

        self.register_outputs({})
