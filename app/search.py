from typing import Optional, List, Tuple
import re

# try package import then fallback to local
try:
    from .search_keyword import build_keyword_node
except Exception:
    from search_keyword import build_keyword_node  # type: ignore

# join quote segments
def quote_full_text(quote) -> str:
    return "".join(seg.text for seg in quote.segments)


# sort results according to sort_mode; people_filter used for added-order sorts
def sort_quotes(results: List[Tuple], *, sort_mode: Optional[str], people_filter) -> List[Tuple]:
    people = None
    if people_filter is None:
        people = None
    else:
        try:
            people = set(people_filter)
        except Exception:
            people = None

    # Default: newest quote if no explicit sort
    if not sort_mode:
        return sorted(results, key=lambda r: (r[1].date, r[1].time, r[1].timestamp or ""), reverse=True)

    if sort_mode == "Newest quote":
        return sorted(results, key=lambda r: (r[1].date, r[1].time, r[1].timestamp or ""), reverse=True)

    if sort_mode == "Oldest quote":
        return sorted(results, key=lambda r: (r[1].date, r[1].time, r[1].timestamp or ""))

    # restrict to entries whose source_file parent folder matches person_name
    def _restrict_to_person_entries(results_list, person_name):
        filtered = [r for r in results_list if r[0].source_file and r[0].source_file.parent.name == person_name]
        return filtered

    if sort_mode == "Newest added (Can only check one!)":
        if people is not None and len(people) == 1:
            person = next(iter(people))
            person_entries = _restrict_to_person_entries(results, person)
            if person_entries:
                return sorted(person_entries, key=lambda r: r[0].line_number, reverse=True)
        return sorted(results, key=lambda r: (r[1].date, r[1].time, r[1].timestamp or ""), reverse=True)

    if sort_mode == "Oldest added (Can only check one!)":
        if people is not None and len(people) == 1:
            person = next(iter(people))
            person_entries = _restrict_to_person_entries(results, person)
            if person_entries:
                return sorted(person_entries, key=lambda r: r[0].line_number)
        return sorted(results, key=lambda r: (r[1].date, r[1].time, r[1].timestamp or ""))

    return results


# simple substring match
def matches_main_search(text: str, query: Optional[str]) -> bool:
    if not query or not query.strip():
        return True
    return query.lower() in text.lower()


# returns filtered + sorted list; main query is substring; keywords is boolean expression
def search_quotes(storage, query: str, *, filters: Optional[dict] = None) -> List[Tuple]:
    filters = filters or {}

    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    char_from = filters.get("char_from")
    char_to = filters.get("char_to")
    people = filters.get("people")
    sort_mode = filters.get("sort")

    # build keyword AST from filters (keywords)
    keywords_field = filters.get("keywords") or filters.get("keyword") or None
    try:
        keyword_node = build_keyword_node(keywords_field) if keywords_field and keywords_field.strip() else None
    except ValueError:
        raise

    results: List[Tuple] = []

    for index in storage.index:
        quote = storage.load_quote(index)
        if not quote:
            continue

        full_text = quote_full_text(quote)

        # main search
        if not matches_main_search(full_text, query):
            continue

        # keyword filter
        if keyword_node:
            try:
                if not keyword_node.evaluate(full_text):
                    continue
            except Exception:
                log.exception("Keyword evaluation failed")
                raise

        # date filter (QDate expected)
        if date_from and quote.date < date_from.toString("yyyy-MM-dd"):
            continue
        if date_to and quote.date > date_to.toString("yyyy-MM-dd"):
            continue

        # people filter
        if people:
            speakers = {seg.speaker for seg in quote.segments if seg.speaker}
            people_set = set(people)
            if not (speakers & people_set):
                continue

        # length filter
        text_len = len(full_text)
        if char_from is not None and text_len < char_from:
            continue
        if char_to is not None and text_len > char_to:
            continue

        results.append((index, quote))

    # sort results
    results = sort_quotes(results, sort_mode=sort_mode, people_filter=people)

    return results