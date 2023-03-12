
from pulumi import ComponentResource, ResourceOptions, Config
import pulumi_aws as aws
from leviathan import consts


class AccountBaseline(ComponentResource):
    def __init__(self, account_id: str) -> None:
        # By calling super(), we ensure any instantiation of this class inherits from the ComponentResource class so we don't have to declare all the same things all over again.
        super().__init__('pkg:leviathan:account_baseline', 'account_baseline', None, opts=None)
        # This definition ensures the new component resource acts like anything else in the Pulumi ecosystem when being called in code.

        # Create an AWS provider with assumed OrganizationAccessRole for this specific account
        config = Config()
        region = config.require('aws:region')
        role_to_assume = f'arn:aws:iam::{account_id}:role/aws-service-role/{consts.OrganizationAccountAccessRoleName}'
        provider = aws.Provider(account_id, region=region, assume_role=role_to_assume)

        # All child resources will use the provider
        child_opts = ResourceOptions(parent=self, providers={'aws' : provider})

        ### Here we are gonna setup account security, networking etc. baseline

        from pulumi_aws import s3

        # Create an AWS resource (S3 Bucket)
        bucket = s3.Bucket('my-bucket', opts=child_opts)


        self.register_outputs({'account' : self.account})
