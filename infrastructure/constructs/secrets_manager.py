from aws_cdk import SecretValue, aws_secretsmanager
from constructs import Construct


class SecretsManager(Construct):
    secret: aws_secretsmanager.Secret

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        name: str,
        description: str,
        secrets: dict[str, str],
    ) -> None:
        """
        Creates a secret in Secrets Manager.

        Parameters
        ----------
        name : str
            Secret name, e.g. "kicksaw-production-api-token".


        """
        super().__init__(scope, id)

        self.secret = aws_secretsmanager.Secret(
            self,
            id,
            description=description,
            secret_name=name,
            secret_object_value={
                key: SecretValue(value) for key, value in secrets.items()
            },
        )

    @property
    def secret_arn(self) -> str:
        return self.secret.secret_arn
