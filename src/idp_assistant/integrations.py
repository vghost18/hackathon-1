"""Explicit, configured external integrations."""
from __future__ import annotations
from typing import Any
import base64,msal,requests
from idp_assistant.config import Settings
class IntegrationError(RuntimeError): pass
def publish_json(endpoint:str,headers:dict[str,str],value:dict[str,Any])->dict[str,Any]:
    if not endpoint.startswith(("https://","http://")): raise IntegrationError("Endpoint must use HTTP or HTTPS.")
    try:
        response=requests.post(endpoint,json=value,headers=headers,timeout=30); return {"status_code":response.status_code,"ok":response.ok,"body":response.text[:2000]}
    except requests.RequestException as exc: raise IntegrationError(str(exc)) from exc
def send_outlook(settings:Settings,recipient:str,subject:str,message:str,attachments:dict[str,bytes])->dict[str,Any]:
    client_id=getattr(settings,"ms_client_id",None); tenant=getattr(settings,"ms_tenant_id",None); secret=getattr(settings,"ms_client_secret",None); sender=getattr(settings,"ms_sender_user",None)
    if not all((client_id,tenant,secret,sender)): raise IntegrationError("Microsoft Graph settings are incomplete.")
    token=msal.ConfidentialClientApplication(client_id,authority=f"https://login.microsoftonline.com/{tenant}",client_credential=secret).acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in token: raise IntegrationError(token.get("error_description","Unable to obtain Graph token."))
    payload={"message":{"subject":subject,"body":{"contentType":"Text","content":message},"toRecipients":[{"emailAddress":{"address":recipient}}],"attachments":[{"@odata.type":"#microsoft.graph.fileAttachment","name":n,"contentBytes":base64.b64encode(b).decode()} for n,b in attachments.items()]},"saveToSentItems":True}
    response=requests.post(f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",headers={"Authorization":f"Bearer {token['access_token']}","Content-Type":"application/json"},json=payload,timeout=30)
    return {"status_code":response.status_code,"ok":response.status_code==202,"body":response.text[:1000]}
