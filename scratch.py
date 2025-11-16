# scratch.py
from deck import Deck

if __name__ == "__main__":
    deck = Deck()
    print("Deck size:", len(deck))
    print("Deal 2 cards:", deck.deal(2))
    print("Deck size after dealing:", len(deck))
