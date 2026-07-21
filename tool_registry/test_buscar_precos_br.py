from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from buscar_precos_br import LOJAS, buscar_precos_br


def _mock_response(results: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"results": results}
    return resp


def test_raises_on_empty_produto():
    with pytest.raises(ValueError):
        buscar_precos_br("")


def test_raises_on_whitespace_produto():
    with pytest.raises(ValueError):
        buscar_precos_br("   ")


def test_queries_all_four_stores_with_site_operator():
    # Arrange
    with patch("buscar_precos_br.requests.get") as mock_get:
        mock_get.return_value = _mock_response([])

        # Act
        buscar_precos_br("i7 11700k")

    # Assert
    assert mock_get.call_count == len(LOJAS)
    queried_sites = {call.kwargs["params"]["q"] for call in mock_get.call_args_list}
    for dominio in LOJAS.values():
        assert any(f"site:{dominio}" in q for q in queried_sites)


def test_aggregates_results_tagged_with_loja():
    # Arrange
    def side_effect(url, params, timeout):
        if "mercadolivre.com.br" in params["q"]:
            return _mock_response([
                {"title": "Intel i7 11700k", "url": "https://mercadolivre.com.br/x", "content": "R$ 1500"}
            ])
        return _mock_response([])

    with patch("buscar_precos_br.requests.get", side_effect=side_effect):
        # Act
        resultados = buscar_precos_br("i7 11700k")

    # Assert
    assert len(resultados) == 1
    assert resultados[0] == {
        "loja": "Mercado Livre",
        "titulo": "Intel i7 11700k",
        "url": "https://mercadolivre.com.br/x",
        "conteudo": "R$ 1500",
    }


def test_skips_store_on_request_exception_without_failing():
    # Arrange
    def side_effect(url, params, timeout):
        if "pichau.com.br" in params["q"]:
            raise requests.ConnectionError("boom")
        return _mock_response([{"title": "t", "url": "u", "content": "c"}])

    with patch("buscar_precos_br.requests.get", side_effect=side_effect):
        # Act
        resultados = buscar_precos_br("i7 11700k")

    # Assert: 3 lojas responderam (Pichau falhou e foi omitida, não derrubou as demais)
    assert len(resultados) == 3
    assert all(r["loja"] != "Pichau" for r in resultados)


def test_skips_store_on_invalid_json():
    # Arrange
    def side_effect(url, params, timeout):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        if "kabum.com.br" in params["q"]:
            resp.json.side_effect = ValueError("invalid json")
        else:
            resp.json.return_value = {"results": []}
        return resp

    with patch("buscar_precos_br.requests.get", side_effect=side_effect):
        # Act / Assert (não deve levantar exceção)
        resultados = buscar_precos_br("i7 11700k")
        assert resultados == []
