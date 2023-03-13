
from pulumi import ComponentResource, ResourceOptions, Output
import pulumi_aws as aws
import pulumi_random as random
from leviathan import consts


class Account(ComponentResource):
    def __init__(self, name: str, opts=None) -> None:
        # By calling super(), we ensure any instantiation of this class inherits from the ComponentResource class so we don't have to declare all the same things all over again.
        super().__init__('pkg:leviathan:account', name, None, opts=opts)
        # This definition ensures the new component resource acts like anything else in the Pulumi ecosystem when being called in code.
        child_opts = ResourceOptions(parent=self)

        random_email_suffix = random.RandomString(
            f'random_email_suffix_for_{name}',
            length=7,
            numeric=False,
            special=False,
            opts=child_opts
            ).result

        self.child_opts = child_opts
        self.account = aws.organizations.Account(
            name,
            name=name,
            # aws account email can't be reused. Ever
            email=Output.concat('dev.rosiv+aws-', name, '-', random_email_suffix, '@gmail.com'),
            close_on_deletion=True,
            iam_user_access_to_billing='ALLOW',
            role_name=consts.OrganizationAccountAccessRoleName,
            opts=child_opts)

        self.register_outputs({'account' : self.account})
