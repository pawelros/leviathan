
from pulumi import ComponentResource, ResourceOptions, Output
import pulumi_aws as aws
import pulumi_random as random
from leviathan import consts
from leviathan.account import Account
from leviathan.account_baseline import EnvironmentBaseline


class Environment(ComponentResource):
    def __init__(self, name: str) -> None:
        # By calling super(), we ensure any instantiation of this class inherits from the ComponentResource class so we don't have to declare all the same things all over again.
        super().__init__('pkg:leviathan:environment', name, None, opts=None)
        # This definition ensures the new component resource acts like anything else in the Pulumi ecosystem when being called in code.
        child_opts = ResourceOptions(parent=self)

        account = Account(name, child_opts)

        self.account = account
        self.baseline = EnvironmentBaseline(name, account.account.id, opts=account.child_opts)

        self.register_outputs({'account' : self.account})
