from pulumi import ComponentResource, ResourceOptions, InvokeOptions
import pulumi_aws as aws
import pulumi
import json
from leviathan.configuration import cidrs
from leviathan.vpc import Vpc


class Routing(ComponentResource):
    def __init__(self, vpc: Vpc, opts) -> None:
        # By calling super(), we ensure any instantiation of this class inherits from the ComponentResource class so we don't have to declare all the same things all over again.
        super().__init__(
            "pkg:leviathan:environments:networking:routing", "routing", None, opts=opts
        )
        # This definition ensures the new component resource acts like anything else in the Pulumi ecosystem when being called in code.
        child_opts = pulumi.ResourceOptions(parent=self, providers=opts.providers)

        # Internet gateway
        self.internet_gateway = aws.ec2.InternetGateway(
            "networking-internet-gateway",
            vpc_id=vpc.id,
            opts=child_opts
        )

        # Route tables
        self.public_route_table = aws.ec2.RouteTable(
            'networking-public-rt',
            vpc_id=vpc.id,
            opts=pulumi.ResourceOptions(parent=self.internet_gateway, providers=child_opts.providers),
        )

        aws.ec2.Route(
            'networking-internet-route',
            gateway_id=self.internet_gateway.id,
            route_table_id=self.public_route_table.id,
            destination_cidr_block=cidrs.EVERYWHERE,
            opts=pulumi.ResourceOptions(parent=self.public_route_table, providers=child_opts.providers),
        )

        aws.ec2.MainRouteTableAssociation(
            'networking-public-main-route-association',
            route_table_id=self.public_route_table.id,
            vpc_id=vpc.id,
            opts=pulumi.ResourceOptions(parent=self.public_route_table, providers=child_opts.providers),
        )

        for index, subnet in enumerate(vpc.public_subnets):
            aws.ec2.RouteTableAssociation(
                f'networking-public-route-association-{index}',
                route_table_id=self.public_route_table.id,
                subnet_id=subnet,
                opts=pulumi.ResourceOptions(parent=self.public_route_table, providers=child_opts.providers),
            )
