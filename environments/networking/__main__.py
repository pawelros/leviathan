import pulumi
from pulumi import ResourceOptions, Config
import pulumi_aws as aws
from pulumi_aws import ProviderAssumeRoleArgs
from leviathan.vpc import Vpc
from leviathan.configuration import cidrs
from routing import Routing

config = pulumi.Config()
stack = pulumi.get_stack()
org = config.require("org")

# TODO: implement json serializer for each CustomResourceComponent
# in order to export crucial properties only and allow to
# easily deserialize entire stack reference into object
stack_root_ref = pulumi.StackReference(f"{org}/leviathan/root")

config = Config("aws")
region = config.require("region")
role_to_assume = stack_root_ref.get_output("networking_account").apply(
    lambda v: f"arn:aws:iam::{v['account']['id']}:role/{v['account']['role_name']}"
)

provider = aws.Provider(
    "networking_aws_provider",
    assume_role=ProviderAssumeRoleArgs(
        role_arn=role_to_assume, session_name="leviathan"
    ),
    region=region,
)

# All child resources will use the provider
child_opts = ResourceOptions(providers={"aws": provider})

vpc = Vpc("main", cidrs.CIDR_PREFIX_NETWORKING, child_opts, is_public=True)
routing = Routing(vpc=vpc, stack_root_ref=stack_root_ref, opts=child_opts)
