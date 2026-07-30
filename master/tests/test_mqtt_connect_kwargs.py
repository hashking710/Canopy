import aiomqtt

from canopy_master import mqtt_subscriber


def test_no_auth_or_tls_by_default(monkeypatch):
    monkeypatch.setattr(mqtt_subscriber, "MQTT_USERNAME", None)
    monkeypatch.setattr(mqtt_subscriber, "MQTT_TLS", False)
    assert mqtt_subscriber._mqtt_connect_kwargs() == {}


def test_includes_username_and_password_when_set(monkeypatch):
    monkeypatch.setattr(mqtt_subscriber, "MQTT_USERNAME", "canopy-master")
    monkeypatch.setattr(mqtt_subscriber, "MQTT_PASSWORD", "s3cret")
    monkeypatch.setattr(mqtt_subscriber, "MQTT_TLS", False)
    kwargs = mqtt_subscriber._mqtt_connect_kwargs()
    assert kwargs == {"username": "canopy-master", "password": "s3cret"}


def test_includes_tls_params_when_enabled(monkeypatch):
    monkeypatch.setattr(mqtt_subscriber, "MQTT_USERNAME", None)
    monkeypatch.setattr(mqtt_subscriber, "MQTT_TLS", True)
    monkeypatch.setattr(mqtt_subscriber, "MQTT_CA_CERT", "/certs/cert.pem")
    kwargs = mqtt_subscriber._mqtt_connect_kwargs()
    assert isinstance(kwargs["tls_params"], aiomqtt.TLSParameters)
    assert kwargs["tls_params"].ca_certs == "/certs/cert.pem"
