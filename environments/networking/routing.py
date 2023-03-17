from pulumi import ComponentResource
import pulumi_aws as aws
import pulumi
from leviathan.configuration import cidrs
from leviathan.vpc import Vpc


class Routing(ComponentResource):
    def __init__(self, vpc: Vpc, stack_root_ref: pulumi.StackReference, opts) -> None:
        # By calling super(), we ensure any instantiation of this class inherits from the ComponentResource class so we don't have to declare all the same things all over again.
        super().__init__(
            "pkg:leviathan:environments:networking:routing", "routing", None, opts=opts
        )
        # This definition ensures the new component resource acts like anything else in the Pulumi ecosystem when being called in code.
        child_opts = pulumi.ResourceOptions(parent=self, providers=opts.providers)

        self._internet_gateway(vpc, child_opts)
        self._nat_gateway(vpc, child_opts)
        self._transit_gateway(vpc, stack_root_ref, child_opts)

        routing_data = {
            "vpc": vpc.id,
            "internet_gateway": self.internet_gateway,
            "nat_gateway": self.nat_gateway,
            "transit_gateway": self.transit_gateway,
        }

        pulumi.export("routing", routing_data)

    def _internet_gateway(self, vpc: Vpc, child_opts: pulumi.ResourceOptions):
        # Internet gateway
        self.internet_gateway = aws.ec2.InternetGateway(
            "networking-internet-gateway",
            vpc_id=vpc.id,
            tags={"Name": "networking-internet-gateway"},
            opts=child_opts,
        )

        # Route tables
        self.public_route_table = aws.ec2.RouteTable(
            "networking-public-rt",
            vpc_id=vpc.id,
            tags={"Name": "networking-public-route-table"},
            opts=pulumi.ResourceOptions(
                parent=self.internet_gateway, providers=child_opts.providers
            ),
        )

        aws.ec2.Route(
            "networking-internet-route",
            gateway_id=self.internet_gateway.id,
            route_table_id=self.public_route_table.id,
            destination_cidr_block=cidrs.EVERYWHERE,
            opts=pulumi.ResourceOptions(
                parent=self.public_route_table, providers=child_opts.providers
            ),
        )

        aws.ec2.MainRouteTableAssociation(
            "networking-public-main-route-association",
            route_table_id=self.public_route_table.id,
            vpc_id=vpc.id,
            opts=pulumi.ResourceOptions(
                parent=self.public_route_table, providers=child_opts.providers
            ),
        )

        for index, subnet in enumerate(vpc.public_subnets):
            aws.ec2.RouteTableAssociation(
                f"networking-public-route-association-{index}",
                route_table_id=self.public_route_table.id,
                subnet_id=subnet,
                opts=pulumi.ResourceOptions(
                    parent=self.public_route_table, providers=child_opts.providers
                ),
            )

    def _nat_gateway(self, vpc: Vpc, child_opts: pulumi.ResourceOptions):
        # NAT Gateway
        # TODO: Create 2nd NAT Gateway in another AZ for HA
        eip = aws.ec2.Eip(
            "networking-nat-eip",
            vpc=True,
            opts=pulumi.ResourceOptions(
                parent=self.public_route_table, providers=child_opts.providers
            ),
        )

        self.nat_gateway = aws.ec2.NatGateway(
            "networking-nat-gw",
            allocation_id=eip.id,
            subnet_id=vpc.public_subnets[0],
            tags={"Name": "networking-nat-gw"},
            opts=pulumi.ResourceOptions(
                parent=self.public_route_table, providers=child_opts.providers
            ),
        )

        # Private route table
        private_route_table = aws.ec2.RouteTable(
            "networking-private-route-table",
            vpc_id=vpc.id,
            tags={"Name": "networking-private-route-table"},
            opts=pulumi.ResourceOptions(parent=vpc, providers=child_opts.providers),
        )

        private_route = aws.ec2.Route(
            "networking-private-route",
            nat_gateway_id=self.nat_gateway.id,
            route_table_id=private_route_table.id,
            destination_cidr_block=cidrs.EVERYWHERE,
            opts=pulumi.ResourceOptions(
                parent=self.nat_gateway, providers=child_opts.providers
            ),
        )

        for index, subnet in enumerate(vpc.private_subnets):
            aws.ec2.RouteTableAssociation(
                f"networking-private-route-table-association-{index}",
                route_table_id=private_route_table,
                subnet_id=subnet,
                opts=pulumi.ResourceOptions(
                    parent=private_route, providers=child_opts.providers
                ),
            )

    def _transit_gateway(
        self,
        vpc: Vpc,
        stack_root_ref: pulumi.StackReference,
        child_opts: pulumi.ResourceOptions,
    ):
        self.transit_gateway = aws.ec2transitgateway.TransitGateway(
            "central-egress-tgtw",
            description="central-egress-tgtw",
            auto_accept_shared_attachments="enable",
            tags={"Name": "central-egress-tgtw"},
            opts=child_opts,
        )

        # associate networking account with Transit Gateway
        self.central_transit_attach = aws.ec2transitgateway.VpcAttachment(
            f"{vpc.name}-transit-gateway-attachment",
            transit_gateway_id=self.transit_gateway.id,
            vpc_id=vpc.id,
            subnet_ids=vpc.private_subnets,
            opts=child_opts,
            tags={"Name": vpc.name},
        )

        # Add a static route in tgtw default route table pointing all traﬃc to egress VPC.
        # Because of this static route, Transit Gateway sends all internet traﬃc through its ENIs
        # in the egress VPC. Once in the egress VPC, traﬃc follows the routes deﬁned in the subnet
        #  route table where these Transit Gateway ENIs are present.
        aws.ec2transitgateway.Route(
            "egress-tgw-route",
            destination_cidr_block="0.0.0.0/0",
            transit_gateway_attachment_id=self.central_transit_attach.id,
            transit_gateway_route_table_id=self.transit_gateway.association_default_route_table_id,
            opts=pulumi.ResourceOptions(
                parent=self.transit_gateway, providers=child_opts.providers
            ),
        )

        # You add a route in subnet route tables pointing all traffic towards the respective NAT gateway
        # in the same Availability Zone to minimize cross-Availability Zone (AZ) traffic. The NAT gateway
        # subnet route table has internet gateway (IGW) as the next hop. For return traffic to ﬂow back,
        # you must add a static route table entry in the NAT gateway subnet route table pointing all spoke
        # VPC bound traffic to Transit Gateway as the next hop.
        aws.ec2.Route(
            "networking-internet-return-route",
            transit_gateway_id=self.transit_gateway.id,
            route_table_id=self.public_route_table.id,
            destination_cidr_block=cidrs.DEFAULT_CIDR_BLOCK,
            opts=pulumi.ResourceOptions(
                depends_on=self.transit_gateway,
                parent=self.public_route_table,
                providers=child_opts.providers,
            ),
        )

        # Share transit gateway with an entire organization
        aws_org_arn = stack_root_ref.get_output("organization")["arn"]

        ram_resource_share = aws.ram.ResourceShare(
            "central-egress-tgtw-share",
            allow_external_principals=False,
            opts=pulumi.ResourceOptions(
                parent=self.transit_gateway, providers=child_opts.providers
            ),
        )

        aws.ram.PrincipalAssociation(
            "central-egress-tgtw-share-principal-assoc",
            principal=aws_org_arn,
            resource_share_arn=ram_resource_share.arn,
            opts=pulumi.ResourceOptions(
                parent=ram_resource_share, providers=child_opts.providers
            ),
        )

        aws.ram.ResourceAssociation(
            "central-egress-tgtw-resource-assoc",
            resource_arn=self.transit_gateway.arn,
            resource_share_arn=ram_resource_share.arn,
            opts=pulumi.ResourceOptions(
                parent=ram_resource_share, providers=child_opts.providers
            ),
        )
