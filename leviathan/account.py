
import time
from pulumi import ComponentResource, ResourceOptions
import pulumi_aws as aws
import pulumi_random as random
from leviathan import consts
from leviathan.account_baseline import AccountBaseline


class Account(ComponentResource):
    def __init__(self, name: str) -> None:
        # By calling super(), we ensure any instantiation of this class inherits from the ComponentResource class so we don't have to declare all the same things all over again.
        super().__init__('pkg:leviathan:account', name, None, opts=None)
        # This definition ensures the new component resource acts like anything else in the Pulumi ecosystem when being called in code.
        child_opts = ResourceOptions(parent=self)

        random_email_suffix = random.RandomString(
            "random_email_suffix",
            length=8,
            numeric=False,
            special=False)

        self.account = aws.organizations.Account(
            name,
            name=name,
            # aws account email can't be reused. Ever
            email=f'dev.rosiv+aws-{name}-{random_email_suffix}@gmail.com',
            close_on_deletion=True,
            iam_user_access_to_billing='ALLOW',
            role_name=consts.OrganizationAccountAccessRoleName,
            opts=child_opts)

        self.baseline = AccountBaseline(self.account.id)

        self.register_outputs({'account' : self.account})
