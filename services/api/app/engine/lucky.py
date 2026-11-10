"""Culture-specific lucky-number snapping. Prices are whole currency units."""

from dataclasses import dataclass


class NoAcceptablePrice(ValueError):
    pass


@dataclass(frozen=True)
class Culture:
    name: str
    lucky_digit: str | None = None
    unlucky_digit: str | None = None


NEUTRAL = Culture("neutral")
MALAYSIAN_CHINESE = Culture("malaysian_chinese", lucky_digit="8", unlucky_digit="4")


def is_insulting(price: int, culture: Culture) -> bool:
    """A repeated or trailing unlucky digit reads as an insult (444, 1044)."""
    d = culture.unlucky_digit
    if d is None:
        return False
    text = str(price)
    return d * 2 in text or text.endswith(d)


def _score(price: int, culture: Culture) -> int:
    d = culture.lucky_digit
    if d is None:
        return 0
    text = str(price)
    trailing = len(text) - len(text.rstrip(d))
    return text.count(d) + trailing


def _allowed(price: int, culture: Culture) -> bool:
    return culture.unlucky_digit is None or culture.unlucky_digit not in str(price)


def snap(
    price: int,
    culture: Culture,
    floor: int = 1,
    ceiling: int | None = None,
    tolerance: float = 0.02,
) -> int:
    """Return the luckiest price near `price`, never outside [floor, ceiling]."""
    top = ceiling if ceiling is not None else max(price, floor) * 2
    if floor > top:
        raise NoAcceptablePrice(f"empty range [{floor}, {top}]")
    target = min(max(price, floor), top)
    if culture.lucky_digit is None and culture.unlucky_digit is None:
        return target

    window = max(1, int(target * tolerance))
    low, high = max(floor, target - window), min(top, target + window)
    nearby = [p for p in range(low, high + 1) if _allowed(p, culture)]
    if nearby:
        return max(nearby, key=lambda p: (_score(p, culture), -abs(p - target)))

    everywhere = [p for p in range(floor, top + 1) if _allowed(p, culture)]
    if everywhere:
        d = culture.lucky_digit
        return min(everywhere, key=lambda p: (not (d and str(p).endswith(d)), abs(p - target)))
    raise NoAcceptablePrice(f"no acceptable price in [{floor}, {top}]")
