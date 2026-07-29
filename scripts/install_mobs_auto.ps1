$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot

function Replace-Once {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Old,
        [Parameter(Mandatory = $true)][string]$New
    )

    $Path = Join-Path $Root $RelativePath
    $Text = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
    $Text = $Text.Replace("`r`n", "`n")
    $Old = $Old.Replace("`r`n", "`n")
    $New = $New.Replace("`r`n", "`n")

    if ($Text.Contains($New)) {
        Write-Host "already patched: $RelativePath"
        return
    }

    $Index = $Text.IndexOf($Old, [System.StringComparison]::Ordinal)
    if ($Index -lt 0) {
        throw "anchor not found in $RelativePath"
    }

    $Updated = $Text.Substring(0, $Index) + $New + $Text.Substring($Index + $Old.Length)
    [System.IO.File]::WriteAllText($Path, $Updated, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "patched: $RelativePath"
}

$Nl = "`n"

Replace-Once -RelativePath 'static/js/modelPicker.js' `
    -Old ("const API_BASE = window.location.origin;" + $Nl) `
    -New (("const API_BASE = window.location.origin;" + $Nl) +
          ("const MOBS_AUTO_MODEL_ID = '__mobs_auto__';" + $Nl) +
          ("const MOBS_GENERAL_MODEL = 'qwen3:8b';" + $Nl) +
          ("const MOBS_CODER_MODEL = 'qwen2.5-coder:7b';" + $Nl))

Replace-Once -RelativePath 'static/js/modelPicker.js' `
    -Old ("    return sortModelObjects(result);" + $Nl) `
    -New (("    const general = result.find(m => m.mid === MOBS_GENERAL_MODEL && !m.stale);" + $Nl) +
          ("    const coder = result.find(m => m.mid === MOBS_CODER_MODEL && !m.stale);" + $Nl) +
          ("    if (general && coder) {" + $Nl) +
          ("      result.unshift({" + $Nl) +
          ("        key: MOBS_AUTO_MODEL_ID," + $Nl) +
          ("        mid: MOBS_AUTO_MODEL_ID," + $Nl) +
          ("        display: 'MOBS Auto'," + $Nl) +
          ("        url: general.url," + $Nl) +
          ("        endpointId: general.endpointId," + $Nl) +
          ("        epName: 'Automatic routing'," + $Nl) +
          ("        category: 'local'," + $Nl) +
          ("        providerText: 'MOBS Auto automatic routing qwen3 coder'," + $Nl) +
          ("        stale: false," + $Nl) +
          ("        offline: false," + $Nl) +
          ("      });" + $Nl) +
          ("    }" + $Nl) +
          ("    return sortModelObjects(result);" + $Nl))

Replace-Once -RelativePath 'static/js/modelPicker.js' `
    -Old ("      const _mlogo = providerLogo(m.mid);" + $Nl) `
    -New ("      const _mlogo = m.mid === MOBS_AUTO_MODEL_ID ? '' : providerLogo(m.mid);" + $Nl)

Replace-Once -RelativePath 'static/js/modelPicker.js' `
    -Old ("      const favDot = document.createElement('button');" + $Nl) `
    -New (("      const favDot = document.createElement('button');" + $Nl) +
          ("      if (m.mid === MOBS_AUTO_MODEL_ID) favDot.style.visibility = 'hidden';" + $Nl))

Replace-Once -RelativePath 'routes/session_routes.py' `
    -Old ("from src.request_models import SessionResponse" + $Nl) `
    -New (("from src.request_models import SessionResponse" + $Nl) +
          ("from src.mobs_auto_router import is_mobs_auto" + $Nl))

Replace-Once -RelativePath 'routes/session_routes.py' `
    -Old (("        if skip_val:" + $Nl) +
          ("            # skip_validation = trust the caller and do NOT probe /v1/models." + $Nl)) `
    -New (("        if is_mobs_auto(model_to_use):" + $Nl) +
          ("            # MOBS Auto is a strategy sentinel, not a provider model." + $Nl) +
          ("            # The concrete route is resolved for each turn in chat_routes." + $Nl) +
          ("            pass" + $Nl) +
          ("        elif skip_val:" + $Nl) +
          ("            # skip_validation = trust the caller and do NOT probe /v1/models." + $Nl))

Replace-Once -RelativePath 'routes/chat_routes.py' `
    -Old ("import asyncio" + $Nl) `
    -New (("import asyncio" + $Nl) + ("import copy" + $Nl))

Replace-Once -RelativePath 'routes/chat_routes.py' `
    -Old ("from src.image_model_ids import looks_like_image_generation_model" + $Nl) `
    -New (("from src.image_model_ids import looks_like_image_generation_model" + $Nl) +
          ("from src.mobs_auto_router import is_mobs_auto, resolve_mobs_auto_route" + $Nl))

$Helper = @'
logger = logging.getLogger(__name__)


def _resolved_mobs_auto_session(
    sess,
    message: str,
    *,
    owner: str | None = None,
    chat_mode: str = "chat",
    tool_intent=None,
    workspace: str = "",
    plan_mode: bool = False,
):
    """Return a shallow execution copy when the session uses MOBS Auto."""
    if not is_mobs_auto(getattr(sess, "model", "")):
        return sess
    route = resolve_mobs_auto_route(
        message,
        owner=owner,
        chat_mode=chat_mode,
        tool_intent=tool_intent,
        workspace=workspace,
        plan_mode=plan_mode,
    )
    execution = copy.copy(sess)
    execution.model = route.model
    execution.endpoint_url = route.endpoint_url
    execution.headers = route.headers
    logger.info(
        "MOBS Auto resolved session=%s model=%s reason=%s fallback=%s",
        getattr(sess, "id", ""), route.model, route.reason, route.used_fallback,
    )
    return execution
'@
$Helper = $Helper.Replace("`r`n", "`n")

Replace-Once -RelativePath 'routes/chat_routes.py' `
    -Old ("logger = logging.getLogger(__name__)" + $Nl) `
    -New ($Helper + $Nl)

Replace-Once -RelativePath 'routes/chat_routes.py' `
    -Old (("        _recover_empty_session_model(sess, session, owner=owner)" + $Nl) +
          ('        if not getattr(sess, "model", "").strip():' + $Nl)) `
    -New (("        _recover_empty_session_model(sess, session, owner=owner)" + $Nl) +
          ("        try:" + $Nl) +
          ("            sess = _resolved_mobs_auto_session(sess, message, owner=owner)" + $Nl) +
          ("        except RuntimeError as exc:" + $Nl) +
          ("            raise HTTPException(503, str(exc))" + $Nl) +
          ('        if not getattr(sess, "model", "").strip():' + $Nl))

Replace-Once -RelativePath 'routes/chat_routes.py' `
    -Old (("            _recover_empty_session_model(sess, session, owner=owner)" + $Nl) +
          ('            if not getattr(sess, "model", "").strip():' + $Nl)) `
    -New (("            _recover_empty_session_model(sess, session, owner=owner)" + $Nl) +
          ("            try:" + $Nl) +
          ("                sess = _resolved_mobs_auto_session(" + $Nl) +
          ("                    sess, message, owner=owner, chat_mode=chat_mode," + $Nl) +
          ("                    tool_intent=_tool_intent, workspace=workspace, plan_mode=plan_mode," + $Nl) +
          ("                )" + $Nl) +
          ("            except RuntimeError as exc:" + $Nl) +
          ("                raise HTTPException(503, str(exc))" + $Nl) +
          ('            if not getattr(sess, "model", "").strip():' + $Nl))

Write-Host 'MOBS Auto integration applied. Review git diff, then rebuild Docker.'