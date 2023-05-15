""" Upgrade Board Types
The authoritative definition document is
https://uwprod.sharepoint.com/:x:/r/sites/icecubeupgrade/_layouts/15/Doc.aspx?sourcedoc=%7B4A2A4B0B-F463-4A0B-98FF-6197EF740538%7D&file=DOM_Type_ID_Jumpers.xlsx&action=default&mobileredirect=true
"""

_boardType = {
    96:  'pDOM',
    113: 'DEgg',
    98:  'mDOM',
    114: 'mDOMRev1',
    64:  'LOM',
    117: 'WOM',
    120: 'RadioRx',
    124: 'RadioTx',
    122: 'PencilBeam',
    121: 'POCAM',
    126: 'Acoustic',
    125: 'SwedenCam',
    123: 'Seismometer',
    115: 'DM-Ice',
    111: 'FOM',
    127: 'Unmodified MMB',
    32:  'MMB Test Setup'
}


def getBoardName(jumpers, lowerCase=False, whitespace=True):
    try:
        boardType = _boardType[jumpers]
    except KeyError:
        boardType = 'dev-0x%X' % jumpers

    if lowerCase:
        boardType = boardType.lower()

    if not whitespace:
        boardType = ''.join(boardType.split())

    return boardType
