from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from canopy_master.auth import is_valid_token
from canopy_master.ws_manager import ws_manager

router = APIRouter(tags=["ws"])


@router.websocket("/ws/live")
async def live_updates(ws: WebSocket) -> None:
    # Browsers can't set custom headers on a WebSocket handshake, so the token (when
    # CANOPY_MASTER_TOKEN is set) travels as a query param instead: /ws/live?token=...
    if not is_valid_token(ws.query_params.get("token")):
        await ws.close(code=1008)  # 1008 = policy violation
        return
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
