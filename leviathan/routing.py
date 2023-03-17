from typing import List
from pulumi import ComponentResource
import pulumi_aws as aws
import pulumi
from leviathan.vpc import Vpc


class Routing(ComponentResource):
    def __init__(self, vpc: Vpc, opts, endpoints: List[str] = None) -> None:
        # By calling super(), we ensure any instantiation of this class inherits from the ComponentResource class so we don't have to declare all the same things all over again.
        super().__init__("pkg:leviathan:routing", "routing", None, opts=opts)
        # This definition ensures the new component resource acts like anything else in the Pulumi ecosystem when being called in code.
        child_opts = pulumi.ResourceOptions(parent=self, providers=opts.providers)

        org = pulumi.Config().require("org")
        stack_ref = pulumi.StackReference(f"{org}/leviathan/networking")
        transit_gateway_id = stack_ref.get_output("routing")["transit_gateway"]["id"]
        egress_vpc_cidr = stack_ref.get_output("vpc_info")["cidr_block"]

        self.central_transit_attach = aws.ec2transitgateway.VpcAttachment(
            f"{vpc.name}-transit-gateway-attachment",
            transit_gateway_id=transit_gateway_id,
            vpc_id=vpc.id,
            subnet_ids=vpc.private_subnets,
            opts=child_opts,
            tags={"Name": vpc.name},
        )

        # Private route table
        private_route_table = aws.ec2.RouteTable(
            f"{vpc.name}-priv-route-table",
            vpc_id=vpc.id,
            tags={
                "Name": f"{vpc.name}-priv-route-table",
                "tgw_attachment": self.central_transit_attach.id,  # wait for transit gateway attachment
            },
            opts=pulumi.ResourceOptions(parent=vpc, providers=child_opts.providers),
        )

        for index, subnet in enumerate(vpc.private_subnets):
            aws.ec2.RouteTableAssociation(
                f"{vpc.name}-private-route-table-association-{index}",
                route_table_id=private_route_table,
                subnet_id=subnet,
                opts=pulumi.ResourceOptions(parent=private_route_table),
            )

        tgw_route = aws.ec2.Route(
            f"{vpc.name}-all-traffic-to-egress-vpc",
            destination_cidr_block=egress_vpc_cidr,
            route_table_id=private_route_table,
            transit_gateway_id=transit_gateway_id,
            opts=pulumi.ResourceOptions(
                parent=private_route_table, providers=child_opts.providers
            ),
        )

        self._interface_endpoints(vpc, private_route_table, child_opts, endpoints)

        routing_data = {
            "vpc": vpc.id,
            "transit_gateway_attachment": self.central_transit_attach,
            "transit_gateway_route": tgw_route,
        }

        pulumi.export("routing", routing_data)

    def _interface_endpoints(
        self,
        vpc: Vpc,
        private_route_table: aws.ec2.RouteTable,
        opts: pulumi.ResourceOptions,
        endpoints: List[str] = None,
    ):
        region = pulumi.Config("aws").require("region")
        # AWS Interface Endpoints Security Group
        if endpoints is not None:
            self.endpoint_sg = aws.ec2.SecurityGroup(
                f"{vpc.name}-endpoint-sg",
                description="Allow TLS inbound traffic for Endpoints",
                vpc_id=vpc.id,
                ingress=[
                    aws.ec2.SecurityGroupIngressArgs(
                        description="TLS from VPC",
                        from_port=443,
                        to_port=443,
                        protocol="tcp",
                        cidr_blocks=[vpc.cidr_block],
                    )
                ],
                egress=[
                    aws.ec2.SecurityGroupEgressArgs(
                        from_port=0,
                        to_port=0,
                        protocol="-1",
                        cidr_blocks=["0.0.0.0/0"],
                        ipv6_cidr_blocks=["::/0"],
                    )
                ],
                opts=pulumi.ResourceOptions(parent=vpc, providers=opts.providers),
            )

            # AWS Interface Endpoints
            for e in endpoints:
                if e == "s3":
                    aws.ec2.VpcEndpoint(
                        f"{vpc.name}-{e}",
                        vpc_id=vpc.id,
                        service_name=f"com.amazonaws.{region}.{e}",
                        vpc_endpoint_type="Gateway",
                        route_table_ids=[private_route_table.id],
                        opts=pulumi.ResourceOptions(
                            parent=vpc, providers=opts.providers
                        ),
                    )
                else:
                    aws.ec2.VpcEndpoint(
                        f"{vpc.name}-{e}",
                        private_dns_enabled=True,
                        security_group_ids=[self.endpoint_sg],
                        service_name=f"com.amazonaws.{region}.{e}",
                        subnet_ids=vpc.private_subnets,
                        vpc_endpoint_type="Interface",
                        vpc_id=vpc.id,
                        opts=pulumi.ResourceOptions(
                            parent=vpc, providers=opts.providers
                        ),
                    )
