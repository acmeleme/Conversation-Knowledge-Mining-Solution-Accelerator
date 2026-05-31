"""
Helper functions for initializing and managing Azure OpenAI client instances.
Supports direct Azure OpenAI access and APIM AI Gateway proxy mode.
"""

import openai
from azure.identity import get_bearer_token_provider
from helpers.azure_credential_utils import get_azure_credential
from common.config.config import Config


def get_azure_openai_client():
    """
    Initializes and returns an Azure OpenAI client.

    When USE_APIM_GATEWAY=true, routes all requests through the APIM endpoint
    using a subscription key. When false, connects directly to Azure OpenAI
    using Managed Identity (DefaultAzureCredential).
    """
    config = Config()

    if config.use_apim_gateway and config.apim_endpoint:
        # APIM Gateway mode: use subscription key auth, APIM handles Managed Identity to Azure OpenAI
        client = openai.AzureOpenAI(
            azure_endpoint=config.apim_endpoint,
            api_version=config.apim_api_version,
            api_key=config.apim_subscription_key,
            default_headers={
                "Ocp-Apim-Subscription-Key": config.apim_subscription_key,
            },
        )
    else:
        # Direct mode: Managed Identity auth directly to Azure OpenAI
        token_provider = get_bearer_token_provider(
            get_azure_credential(client_id=config.azure_client_id),
            "https://cognitiveservices.azure.com/.default",
        )
        client = openai.AzureOpenAI(
            azure_endpoint=config.azure_openai_endpoint,
            api_version=config.azure_openai_api_version,
            azure_ad_token_provider=token_provider,
        )

    return client
