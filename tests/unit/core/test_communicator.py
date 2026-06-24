"""Tests for core/communication/communicator.py"""

import json
import struct
from unittest.mock import patch, MagicMock
from typing import Optional, Dict, Any

import pytest

from core.communication.communicator import ClientCommunicator


class TestProtocolConstants:
    def test_protocol_magic(self):
        comm = ClientCommunicator("127.0.0.1", 9999, "test_pwd", timeout=5)
        assert comm.protocol_magic == b"ARKS"
        assert comm.protocol_version == 1


class TestCipher:
    def test_create_cipher_returns_fernet(self):
        comm = ClientCommunicator("127.0.0.1", 9999, "test_password", timeout=5)
        assert comm.cipher is not None
        assert hasattr(comm.cipher, "encrypt")
        assert hasattr(comm.cipher, "decrypt")

    def test_create_cipher_deterministic(self):
        comm1 = ClientCommunicator("127.0.0.1", 9999, "same_pwd", timeout=5)
        comm2 = ClientCommunicator("127.0.0.1", 9999, "same_pwd", timeout=5)
        data = b"hello"
        e1 = comm1.cipher.encrypt(data)
        e2 = comm2.cipher.encrypt(data)
        # Different IVs produce different ciphertexts, but same key
        d1 = comm1.cipher.decrypt(e1)
        d2 = comm2.cipher.decrypt(e2)
        assert d1 == d2 == data

    def test_different_password_different_key(self):
        comm1 = ClientCommunicator("127.0.0.1", 9999, "pwd1", timeout=5)
        comm2 = ClientCommunicator("127.0.0.1", 9999, "pwd2", timeout=5)
        data = b"hello"
        e1 = comm1.cipher.encrypt(data)
        with pytest.raises(Exception):
            comm2.cipher.decrypt(e1)


class TestPackUnpack:
    def test_pack_message_format(self):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        payload = b"test_data"
        packed = comm._pack_message(payload)
        assert packed[:4] == b"ARKS"
        assert packed[4] == 1  # version byte
        assert len(packed) == 4 + 1 + 4 + len(payload)

    def test_pack_message_data_length(self):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        payload = b"x" * 100
        packed = comm._pack_message(payload)
        data_len = struct.unpack('!I', packed[5:9])[0]
        assert data_len == 100

    def test_unpack_message_valid(self):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        payload = b"hello world"
        packed = comm._pack_message(payload)
        unpacked = comm._unpack_message(packed)
        assert unpacked == payload

    def test_unpack_message_too_short(self):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        result = comm._unpack_message(b"short")
        assert result is None

    def test_unpack_message_wrong_magic(self):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        data = b"XXXX" + struct.pack('B', 1) + struct.pack('!I', 5) + b"hello"
        result = comm._unpack_message(data)
        assert result is None

    def test_unpack_message_wrong_version(self):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        data = b"ARKS" + struct.pack('B', 99) + struct.pack('!I', 5) + b"hello"
        result = comm._unpack_message(data)
        assert result is None

    def test_unpack_message_incomplete_body(self):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        header = b"ARKS" + struct.pack('B', 1) + struct.pack('!I', 100)
        data = header + b"too_short"
        result = comm._unpack_message(data)
        assert result is None

    def test_pack_unpack_roundtrip_large_data(self):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        payload = b"A" * 10000
        packed = comm._pack_message(payload)
        unpacked = comm._unpack_message(packed)
        assert unpacked == payload

    def test_pack_unpack_roundtrip_empty(self):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        payload = b""
        packed = comm._pack_message(payload)
        unpacked = comm._unpack_message(packed)
        assert unpacked == payload


class TestSendRequest:
    def test_send_request_network_error(self):
        comm = ClientCommunicator("127.0.0.1", 1, "pwd", timeout=1)
        result = comm.send_request("test", {"key": "value"})
        assert result is None

    def test_send_request_login_no_retry(self):
        comm = ClientCommunicator("127.0.0.1", 1, "pwd", timeout=1)
        result = comm.send_request("login", {"user": "test"})
        assert result is None

    @patch("socket.socket")
    def test_send_request_success(self, mock_socket):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        mock_sock_instance = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock_instance

        response_data = {"status": "success", "reply": "ok"}
        response_json = json.dumps(response_data).encode("utf-8")
        encrypted = comm.cipher.encrypt(response_json)
        packed_response = comm._pack_message(encrypted)

        mock_sock_instance.recv.side_effect = [
            packed_response[:9],
            packed_response[9:],
        ]

        result = comm.send_request("agent_chat", {"instruction": "hello"})
        assert result is not None
        assert result["status"] == "success"

    @patch("socket.socket")
    def test_send_request_retry_on_failure(self, mock_socket):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        comm.is_logged_in = True
        comm.max_retries = 2
        comm.retry_delay = 0.01

        mock_sock_instance = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock_instance
        mock_sock_instance.recv.side_effect = ConnectionError("reset")

        result = comm.send_request("agent_chat", {"instruction": "hello"})
        assert result is None

    @patch("socket.socket")
    def test_send_request_login_no_retry_on_failure(self, mock_socket):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        comm.max_retries = 3
        comm.retry_delay = 0.01

        mock_sock_instance = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock_instance
        mock_sock_instance.recv.side_effect = ConnectionError("reset")

        result = comm.send_request("login", {"user": "test"})
        assert result is None


class TestAuthentication:
    def test_is_authenticated_default_false(self):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        assert comm.is_authenticated() is False

    def test_set_logged_in(self):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        comm.set_logged_in(True)
        assert comm.is_authenticated() is True
        comm.set_logged_in(False)
        assert comm.is_authenticated() is False


class TestGetAvailableModels:
    @patch.object(ClientCommunicator, "send_request")
    def test_get_available_models_success(self, mock_send):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        mock_send.return_value = {
            "status": "success",
            "models": ["qwen3.5-2b", "qwen3.5-9b"],
        }
        result = comm.get_available_models("session_123")
        assert result is not None
        assert result["status"] == "success"
        assert len(result["models"]) == 2

    @patch.object(ClientCommunicator, "send_request")
    def test_get_available_models_failure(self, mock_send):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        mock_send.return_value = {"status": "error", "message": "session expired"}
        result = comm.get_available_models("session_bad")
        assert result["status"] == "error"

    @patch.object(ClientCommunicator, "send_request")
    def test_get_available_models_no_response(self, mock_send):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        mock_send.return_value = None
        result = comm.get_available_models("session_bad")
        assert result is None


class TestRegisterClient:
    @patch.object(ClientCommunicator, "send_request")
    def test_register_client_success(self, mock_send):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        mock_send.return_value = {
            "status": "success",
            "assigned_model": "qwen3.5-2b",
        }
        result = comm.register_client("explorer")
        assert result is not None
        assert result["status"] == "success"

    @patch.object(ClientCommunicator, "send_request")
    def test_register_client_with_preferred_model(self, mock_send):
        comm = ClientCommunicator("127.0.0.1", 9999, "pwd", timeout=5)
        mock_send.return_value = {
            "status": "success",
            "assigned_model": "qwen3.5-9b",
        }
        result = comm.register_client("explorer", preferred_model="qwen3.5-9b")
        assert result is not None
        call_args = mock_send.call_args[0][1]
        assert call_args["preferred_model"] == "qwen3.5-9b"