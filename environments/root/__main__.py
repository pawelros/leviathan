"""An AWS Python Pulumi program"""

import pulumi
from leviathan.account import Account

# create environments

environments = {
    'dev' : Account('dev')
}

# Export the name of the bucket
pulumi.export('environments', environments)
