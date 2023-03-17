from pulumi import ComponentResource, ResourceOptions, InvokeOptions
import pulumi_aws as aws
import pulumi_random as random
from leviathan import consts


class Iam(ComponentResource):
    def __init__(self, name: str, opts=None) -> None:
        # By calling super(), we ensure any instantiation of this class inherits from the ComponentResource class so we don't have to declare all the same things all over again.
        super().__init__("pkg:leviathan:iam", name, None, opts=opts)
        # This definition ensures the new component resource acts like anything else in the Pulumi ecosystem when being called in code.
        child_opts = ResourceOptions(parent=self)

        ec2_assume_role = aws.iam.get_policy_document(
            statements=[
                aws.iam.GetPolicyDocumentStatementArgs(
                    effect="Allow",
                    principals=[
                        aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                            type="Service",
                            identifiers=["ec2.amazonaws.com"],
                        )
                    ],
                    actions=["sts:AssumeRole"],
                )
            ],
            opts=InvokeOptions(parent=self, provider=opts.providers["aws"])
        )

        role = aws.iam.Role(
            f"{name}-ec2-ssm-role",
            path="/",
            assume_role_policy=ec2_assume_role.json,
            opts=child_opts
        )

        aws.iam.InstanceProfile(
            f"{name}-ec2-ssm-instance-profile",
            role=role.name,
            opts=ResourceOptions(parent=role, providers=child_opts.providers)
        )

        aws.iam.RolePolicyAttachment(
            f"{name}-ec2-ssm-core-role-policy-attachment",
            role=role,
            policy_arn=aws.iam.ManagedPolicy.AMAZON_SSM_MANAGED_INSTANCE_CORE,
            opts=ResourceOptions(parent=role, providers=child_opts.providers)
        )

        self.register_outputs({})
