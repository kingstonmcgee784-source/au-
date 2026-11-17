"""Parse SEC Form 4 (statement of changes in beneficial ownership) XML.

Pure functions with no I/O. Follows the EDGAR ownership XML schema
(`ownershipDocument`, schema versions X0306 to X0609).

Only non-derivative transactions (actual shares bought, sold, granted or
withheld) are extracted. Derivative rows, such as option grants, are not
share trades.

Rule 10b5-1: since April 2023, Form 4 has a checkbox (`aff10b5One`) for
trades made under a pre-arranged 10b5-1 plan. Older filings often say so in a
footnote instead. A trade is marked as planned if either says so, as not
planned if the checkbox is present and unticked, and as unknown otherwise.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date

TRANSACTION_CODES = {
    "P": "Open-market purchase",
    "S": "Open-market sale",
    "A": "Grant or award",
    "D": "Disposition to the issuer",
    "F": "Shares withheld for tax",
    "G": "Gift",
    "M": "Option exercise",
    "X": "Option exercise",
    "C": "Conversion",
    "J": "Other",
}

# Refuse documents that declare a DTD or entities: Form 4 never needs them,
# and refusing them rules out entity-expansion attacks on the XML parser.
_UNSAFE = re.compile(r"<!DOCTYPE|<!ENTITY", re.IGNORECASE)
_PLAN = re.compile(r"10b5-?1", re.IGNORECASE)


class Form4ParseError(ValueError):
    pass


@dataclass(frozen=True)
class InsiderTrade:
    owner_name: str
    owner_role: str
    transaction_date: date
    code: str
    acquired: bool  # True = acquired (A), False = disposed (D)
    shares: float
    price: float | None
    shares_after: float | None
    direct: bool | None
    under_10b5_1: bool | None
    security: str


@dataclass(frozen=True)
class Form4:
    owner_name: str
    owner_role: str
    trades: list[InsiderTrade]


def parse_form4(xml_text: str) -> Form4:
    if _UNSAFE.search(xml_text):
        raise Form4ParseError("Form 4 document declares a DTD or entities; refusing to parse")
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError as exc:
        raise Form4ParseError(f"Form 4 is not valid XML: {exc}") from exc
    if root.tag != "ownershipDocument":
        raise Form4ParseError("Not an ownership document")

    owner_name, owner_role = _owners(root)
    plan_box = _flag(root.findtext("aff10b5One"))
    footnotes = {
        note.get("id", ""): " ".join(note.itertext())
        for note in root.iterfind("footnotes/footnote")
    }

    trades: list[InsiderTrade] = []
    for row in root.iterfind("nonDerivativeTable/nonDerivativeTransaction"):
        when = _date(_value(row, "transactionDate"))
        code = (row.findtext("transactionCoding/transactionCode") or "").strip().upper()
        shares = _number(_value(row, "transactionAmounts/transactionShares"))
        direction = (_value(row, "transactionAmounts/transactionAcquiredDisposedCode") or "").upper()
        if when is None or not code or shares is None or direction not in {"A", "D"}:
            continue

        referenced = {ref.get("id", "") for ref in row.iter("footnoteId")}
        mentions_plan = any(_PLAN.search(footnotes.get(ref, "")) for ref in referenced)
        if plan_box is True or mentions_plan:
            under_plan: bool | None = True
        elif plan_box is False:
            under_plan = False
        else:
            under_plan = None

        ownership = _value(row, "ownershipNature/directOrIndirectOwnership")
        trades.append(
            InsiderTrade(
                owner_name=owner_name,
                owner_role=owner_role,
                transaction_date=when,
                code=code,
                acquired=direction == "A",
                shares=shares,
                price=_number(_value(row, "transactionAmounts/transactionPricePerShare")),
                shares_after=_number(
                    _value(row, "postTransactionAmounts/sharesOwnedFollowingTransaction")
                ),
                direct=None if ownership is None else ownership.upper() == "D",
                under_10b5_1=under_plan,
                security=(_value(row, "securityTitle") or "").strip(),
            )
        )
    return Form4(owner_name=owner_name, owner_role=owner_role, trades=trades)


def _owners(root: ET.Element) -> tuple[str, str]:
    names: list[str] = []
    roles: list[str] = []
    for owner in root.iterfind("reportingOwner"):
        name = (owner.findtext("reportingOwnerId/rptOwnerName") or "").strip()
        if name:
            names.append(name)
        rel = owner.find("reportingOwnerRelationship")
        if rel is None:
            continue
        if _flag(rel.findtext("isOfficer")):
            title = (rel.findtext("officerTitle") or "").strip()
            roles.append(title or "Officer")
        if _flag(rel.findtext("isDirector")):
            roles.append("Director")
        if _flag(rel.findtext("isTenPercentOwner")):
            roles.append("10% owner")
        if _flag(rel.findtext("isOther")):
            other = (rel.findtext("otherText") or "").strip()
            roles.append(other or "Other")
    unique_roles = list(dict.fromkeys(roles))
    return " / ".join(names) or "Unknown", ", ".join(unique_roles) or "Unknown"


def _value(element: ET.Element, path: str) -> str | None:
    """Form 4 wraps most fields as <field><value>…</value></field>."""
    node = element.find(f"{path}/value")
    if node is None:
        node = element.find(path)
    if node is None or node.text is None:
        return None
    return node.text.strip() or None


def _flag(text: str | None) -> bool | None:
    if text is None:
        return None
    value = text.strip().lower()
    if value in {"1", "true"}:
        return True
    if value in {"0", "false"}:
        return False
    return None


def _number(text: str | None) -> float | None:
    if text is None:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
