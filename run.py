import os

from function import create_app


app = create_app()

# systemctl --user restart erp-gateway.service
# systemctl --user --no-pager --full status erp-gateway.service
# journalctl --user -u erp-gateway.service -f

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
