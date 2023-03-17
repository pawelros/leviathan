from pulumi import ComponentResource, ResourceOptions, Config
import pulumi_aws as aws
from leviathan import consts
from leviathan.account import Account
from leviathan.vpc import Vpc
from leviathan.routing import Routing
from leviathan.iam import Iam
from leviathan.configuration import cidrs


class Environment(ComponentResource):
    def __init__(self, name: str) -> None:
        # By calling super(), we ensure any instantiation of this class inherits from the ComponentResource class so we don't have to declare all the same things all over again.
        super().__init__("pkg:leviathan:environment", name, None, opts=None)
        # This definition ensures the new component resource acts like anything else in the Pulumi ecosystem when being called in code.
        child_opts = ResourceOptions(parent=self)

        account = Account(name, child_opts)

        self.account = account

        # Create an AWS provider with assumed OrganizationAccessRole for this specific account
        config = Config("aws")
        region = config.require("region")
        role_to_assume = account.account.id.apply(
            lambda v: f"arn:aws:iam::{v}:role/{consts.OrganizationAccountAccessRoleName}"
        )

        provider = aws.Provider(
            f"{name}_aws_provider",
            assume_role=aws.ProviderAssumeRoleArgs(
                role_arn=role_to_assume, session_name="leviathan"
            ),
            region=region,
            opts=child_opts,
        )

        # All child resources will use the provider
        child_opts = ResourceOptions(parent=self, providers={"aws": provider})

        self.vpc = Vpc(
            name, eval(f"cidrs.CIDR_PREFIX_{name.upper()}"), child_opts, is_public=False
        )

        self.routing = Routing(
            self.vpc,
            child_opts,
            endpoints=[
                "ec2",
                "ec2messages",
                "ssm",
                "ssmmessages",
                "s3",
                "ecr.dkr",
                "ecs",
                "ecs-agent",
                "ecs-telemetry",
            ],
        )

        Iam(name, child_opts)

        self.register_outputs({"account": self.account, "vpc": self.vpc})
