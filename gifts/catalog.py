GIFT_CATALOG = [
    {
        "id": "pawn",
        "name": "Pawn Spark",
        "piece": "Pawn",
        "description": "A simple show of support for a great move or a great friend.",
        "price_usd": 1,
    },
    {
        "id": "knight",
        "name": "Knight Leap",
        "piece": "Knight",
        "description": "For sharp tactics, brave sacrifices, and surprise counterplay.",
        "price_usd": 5,
    },
    {
        "id": "bishop",
        "name": "Bishop Line",
        "piece": "Bishop",
        "description": "A clean diagonal gift for players with elegant style.",
        "price_usd": 10,
    },
    {
        "id": "rook",
        "name": "Rook Tower",
        "piece": "Rook",
        "description": "A bigger statement for loyal training partners and rivals.",
        "price_usd": 25,
    },
    {
        "id": "queen",
        "name": "Queen's Glory",
        "piece": "Queen",
        "description": "A premium gift for standout performances and community stars.",
        "price_usd": 100,
    },
    {
        "id": "king",
        "name": "King's Crown",
        "piece": "King",
        "description": "Reserved for top-tier respect, celebrations, and big moments.",
        "price_usd": 500,
    },
    {
        "id": "royal-board",
        "name": "Royal Board",
        "piece": "Collector",
        "description": "A prestige collectible gift for community leaders and champions.",
        "price_usd": 1000,
    },
    {
        "id": "checkmate-throne",
        "name": "Checkmate Throne",
        "piece": "Legend",
        "description": "The flagship gift for unforgettable matches and major celebrations.",
        "price_usd": 5000,
    },
]

GIFT_LOOKUP = {gift["id"]: gift for gift in GIFT_CATALOG}


def get_gift_catalog_item(gift_id: str):
    return GIFT_LOOKUP.get(gift_id)
