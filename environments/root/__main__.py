"""An AWS Python Pulumi program"""

import pulumi
import pulumi_aws as aws
from leviathan.account import Account
from leviathan.environment import Environment

# The Networking account serves as the central hub for network routing between
# AMS multi-account landing zone accounts, your on-premises network,
# and egress traffic out to the Internet.

networking_account = Account("networking")

# create development environments

environments = {"dev": Environment("dev")}

org = aws.organizations.get_organization()

# Export the name of the bucket
pulumi.export("organization", {"id": org.id, "arn": org.arn})
pulumi.export("environments", environments)
pulumi.export("networking_account", networking_account)
