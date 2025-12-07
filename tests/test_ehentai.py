"""
Unit tests for E-Hentai utility functions.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from utils.ehentai import get_gdata, get_GP_cost, _get_base_url

# Mock HTML responses
HTML_GP_NORMAL = """
<div id="db">
    <div>
        <strong>1000</strong> GP
        <br>
        <strong>2000</strong> GP
    </div>
    <div>
        <strong>3000</strong> GP
        <br>
        <strong>4000</strong> GP
    </div>
</div>
"""

HTML_GP_FREE = """
<div id="db">
    <div>
        <strong>100 MiB</strong>
        <br>
        <strong>200 MiB</strong>
    </div>
    <div>
        <strong>Free!</strong>
    </div>
    <div>
        <strong>300 MiB</strong>
    </div>
</div>
"""

@pytest.mark.asyncio
async def test_get_gdata():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"gmetadata": [{"gid": 123, "title": "Test"}]}
    
    with patch('utils.ehentai.http.post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        
        result = await get_gdata(123, "token")
        
        assert result["gid"] == 123
        assert result["title"] == "Test"
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_get_gp_cost_normal():
    """Test GP cost parsing for normal gallery."""
    mock_resp = MagicMock()
    mock_resp.text = HTML_GP_NORMAL
    
    with patch('utils.ehentai.http.post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        
        costs = await get_GP_cost(123, "token")
        
        # Based on logic: GPs[0].text digits -> org, GPs[2].text digits -> res
        # GPs in HTML_GP_NORMAL:
        # 0: 1000
        # 1: 2000
        # 2: 3000
        # 3: 4000
        
        # Wait, BeautifulSoup find_all("strong") order matters.
        # Structure:
        # <div> <strong>1000</strong> ... <strong>2000</strong> </div>
        # <div> <strong>3000</strong> ... <strong>4000</strong> </div>
        
        assert costs["org"] == "1000"
        assert costs["res"] == "3000"
        # pre is calculated from res: 3000 * 1.3 = 3900
        assert costs["pre"] == 3900

@pytest.mark.asyncio
async def test_get_gp_cost_free():
    """Test GP cost parsing for Free! gallery (calculated from size)."""
    mock_resp = MagicMock()
    mock_resp.text = HTML_GP_FREE
    
    with patch('utils.ehentai.http.post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        
        # Logic:
        # GPs[2].text == "Free!"
        # org = round(convert_to_mib(GPs[1].text)) -> "200 MiB" -> 200 * 21 = 4200 ? 
        # Wait, logic in ehentai.py:
        # return (size * conversion_factors[unit]) * 21
        # 200 MiB -> 200 * 1 * 21 = 4200
        
        # res = round(convert_to_mib(GPs[3].text)) -> "300 MiB" -> 300 * 21 = 6300
        
        # Wait, GPs indices:
        # 0: 100 MiB
        # 1: 200 MiB (Actually, HTML usually has explicit labels)
        # Assuming find_all returns them in order.
        
        # Let's verify convert_to_mib logic via the test results.
        
        costs = await get_GP_cost(123, "token")
        
        # org comes from GPs[1] ("200 MiB") -> 200 * 21 = 4200
        # res comes from GPs[3] ("300 MiB") -> 300 * 21 = 6300
        # pre = res * 1.3 = 6300 * 1.3 = 8190
        
        assert costs["org"] == 4200
        assert costs["res"] == 6300
        assert costs["pre"] == 8190

def test_get_base_url():
    with patch('utils.ehentai.httpx.get') as mock_get:
        # Test EX success
        mock_get.return_value.text = "ExHentai"
        assert _get_base_url() == "https://exhentai.org"
        
        # Test EX fail (empty)
        mock_get.return_value.text = ""
        assert _get_base_url() == "https://e-hentai.org"
        
        # Test EX exception
        mock_get.side_effect = Exception("Error")
        assert _get_base_url() == "https://e-hentai.org"
