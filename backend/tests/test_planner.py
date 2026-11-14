"""Tests for SIA XML parsing, pass clustering, and balanced per-(pass, detector) selection."""

from app.data.planner import group_passes, select
from app.data.sia import parse_votable


SAMPLE_SIA_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
  <RESOURCE type="results">
    <TABLE>
      <FIELD name="obs_id" datatype="char"/>
      <FIELD name="energy_bandpassname" datatype="char"/>
      <FIELD name="t_min" datatype="double"/>
      <FIELD name="t_max" datatype="double"/>
      <FIELD name="em_min" datatype="double"/>
      <FIELD name="em_max" datatype="double"/>
      <FIELD name="access_url" datatype="char"/>
      <DATA><TABLEDATA>
        <TR><TD>o1</TD><TD>SPHEREx-D3</TD><TD>60903.0</TD><TD>60903.01</TD><TD>1.6e-6</TD><TD>2.4e-6</TD><TD>https://x/o1</TD></TR>
        <TR><TD>o2</TD><TD>SPHEREx-D3</TD><TD>60910.0</TD><TD>60910.01</TD><TD>1.6e-6</TD><TD>2.4e-6</TD><TD>https://x/o2</TD></TR>
        <TR><TD>o3</TD><TD>SPHEREx-D3</TD><TD>60920.0</TD><TD>60920.01</TD><TD>1.6e-6</TD><TD>2.4e-6</TD><TD>https://x/o3</TD></TR>
        <TR><TD>o4</TD><TD>SPHEREx-D3</TD><TD>60940.0</TD><TD>60940.01</TD><TD>1.6e-6</TD><TD>2.4e-6</TD><TD>https://x/o4</TD></TR>
        <TR><TD>o5</TD><TD>SPHEREx-D3</TD><TD>61110.5</TD><TD>61110.51</TD><TD>1.6e-6</TD><TD>2.4e-6</TD><TD>https://x/o5</TD></TR>
        <TR><TD>o6</TD><TD>SPHEREx-D3</TD><TD>61140.0</TD><TD>61140.01</TD><TD>1.6e-6</TD><TD>2.4e-6</TD><TD>https://x/o6</TD></TR>
        <TR><TD>o7</TD><TD>SPHEREx-D5</TD><TD>61270.0</TD><TD>61270.01</TD><TD>3.8e-6</TD><TD>4.4e-6</TD><TD>https://x/o7</TD></TR>
      </TABLEDATA></DATA>
    </TABLE>
  </RESOURCE>
</VOTABLE>
"""


def test_parse_votable_and_group_passes() -> None:
    recs = parse_votable(SAMPLE_SIA_XML, "spherex_dr1")
    assert len(recs) == 7
    assert recs[0].detector == 3
    assert recs[6].detector == 5

    passes, pass_map = group_passes(recs, gap_days=45.0)
    assert len(passes) == 3
    assert passes[0].n_exposures == 4
    assert passes[1].n_exposures == 2
    assert passes[2].n_exposures == 1

    # Budget=2 keeps endpoints of Pass 1 plus all of Pass 2 (2) and Pass 3 (1) -> 5 total
    chosen = select(recs, pass_map, per_pass_det=2)
    ids = [r.obs_id for r in chosen]
    assert ids == ["o1", "o4", "o5", "o6", "o7"]
