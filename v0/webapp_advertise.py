from zeroconf import ServiceInfo, Zeroconf
import socket

# Desired mDNS hostname (must end with a dot)
service_hostname = "jarvis.local."

service_type = "_http._tcp.local."
service_name = "Jarvis Web UI." + service_type
port = 8080
desc = {"path": "/"}

# Get local IP address
local_ip = socket.gethostbyname(socket.gethostname())

info = ServiceInfo(
    service_type,
    service_name,
    addresses=[socket.inet_aton(local_ip)],
    port=port,
    properties=desc,
    server=service_hostname,
)

zeroconf = Zeroconf()
zeroconf.register_service(info)
print(f"Registered mDNS service as {service_hostname} on port {port}")

# Run your Flask app (be sure to unregister when shutting down)
try:
    # Disable the auto-reloader so the service only registers once.
    from webapp import app
    app.run(debug=True, host="0.0.0.0", port=port, use_reloader=False)
finally:
    zeroconf.unregister_service(info)
    zeroconf.close()