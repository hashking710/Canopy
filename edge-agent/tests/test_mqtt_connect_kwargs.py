import aiomqtt

from canopy_agent.services import mqtt_publisher


def test_no_auth_or_tls_by_default(monkeypatch):
    monkeypatch.setattr(mqtt_publisher, "MQTT_USERNAME", None)
    monkeypatch.setattr(mqtt_publisher, "MQTT_TLS", False)
    assert mqtt_publisher.mqtt_connect_kwargs() == {}


def test_includes_username_and_password_when_set(monkeypatch):
    monkeypatch.setattr(mqtt_publisher, "MQTT_USERNAME", "canopy-edge-agent")
    monkeypatch.setattr(mqtt_publisher, "MQTT_PASSWORD", "s3cret")
    monkeypatch.setattr(mqtt_publisher, "MQTT_TLS", False)
    kwargs = mqtt_publisher.mqtt_connect_kwargs()
    assert kwargs == {"username": "canopy-edge-agent", "password": "s3cret"}


def test_includes_tls_params_when_enabled(monkeypatch):
    monkeypatch.setattr(mqtt_publisher, "MQTT_USERNAME", None)
    monkeypatch.setattr(mqtt_publisher, "MQTT_TLS", True)
    monkeypatch.setattr(mqtt_publisher, "MQTT_CA_CERT", "/certs/cert.pem")
    kwargs = mqtt_publisher.mqtt_connect_kwargs()
    assert isinstance(kwargs["tls_params"], aiomqtt.TLSParameters)
    assert kwargs["tls_params"].ca_certs == "/certs/cert.pem"


def test_auth_and_tls_combine(monkeypatch):
    monkeypatch.setattr(mqtt_publisher, "MQTT_USERNAME", "canopy-edge-agent")
    monkeypatch.setattr(mqtt_publisher, "MQTT_PASSWORD", "s3cret")
    monkeypatch.setattr(mqtt_publisher, "MQTT_TLS", True)
    monkeypatch.setattr(mqtt_publisher, "MQTT_CA_CERT", "/certs/cert.pem")
    kwargs = mqtt_publisher.mqtt_connect_kwargs()
    assert kwargs["username"] == "canopy-edge-agent"
    assert kwargs["password"] == "s3cret"
    assert isinstance(kwargs["tls_params"], aiomqtt.TLSParameters)
