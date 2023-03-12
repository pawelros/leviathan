
from pulumi import ComponentResource, ResourceOptions, Config, Output
import pulumi_aws as aws
from pulumi_aws import ProviderAssumeRoleArgs
from leviathan import consts


class AccountBaseline(ComponentResource):
    def __init__(self, account_name: str, account_id: int, opts: ResourceOptions) -> None:
        # By calling super(), we ensure any instantiation of this class inherits from the ComponentResource class so we don't have to declare all the same things all over again.
        super().__init__('pkg:leviathan:account_baseline', 'account_baseline', None, opts=opts)
        # This definition ensures the new component resource acts like anything else in the Pulumi ecosystem when being called in code.

        # Create an AWS provider with assumed OrganizationAccessRole for this specific account
        config = Config('aws')
        region = config.require('region')
        role_to_assume = account_id.apply(lambda v: f"arn:aws:iam::{v}:role/{consts.OrganizationAccountAccessRoleName}")

        provider = aws.Provider(
            f'{account_name}_aws_provider',
            assume_role=ProviderAssumeRoleArgs(role_arn=role_to_assume, session_name='leviathan'),
            region=region,
            opts=opts)

        # All child resources will use the provider
        child_opts = ResourceOptions(parent=self, providers={'aws' : provider})

        ### Here we are gonna setup account security, networking etc. baseline

        from pulumi_aws import s3

        # Create an AWS resource (S3 Bucket)
        bucket = s3.Bucket('environment-bucket', opts=child_opts)


        self.register_outputs({})
