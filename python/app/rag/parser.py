from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from bs4 import BeautifulSoup


@dataclass
class ParsedBlock:
    block_type: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


FENCED_CODE_RE = re.compile(r"```(?P<lang>[a-zA-Z0-9_+-]*)\n(?P<code>.*?)```", re.DOTALL)
MD_IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def parse_blog_content(title: str, summary: str, tags: str, content: str) -> list[ParsedBlock]:
    raw = "\n".join(part for part in [title, summary, tags, content] if part)
    raw = _html_to_markdownish(raw)
    blocks: list[ParsedBlock] = []
    cursor = 0
    current_heading = title

    for match in FENCED_CODE_RE.finditer(raw):
        blocks.extend(_parse_text_and_images(raw[cursor : match.start()], current_heading))
        lang = match.group("lang") or "text"
        code = match.group("code").strip()
        if code:
            blocks.append(
                ParsedBlock(
                    "code",
                    f"Code language: {lang}\n{code}",
                    {"heading": current_heading, "language": lang},
                )
            )
        cursor = match.end()

    blocks.extend(_parse_text_and_images(raw[cursor:], current_heading))
    enriched: list[ParsedBlock] = []
    for block in blocks:
        heading = _extract_heading(block.text)
        if heading:
            current_heading = heading
        block.metadata.setdefault("heading", current_heading)
        enriched.append(block)
    return [block for block in enriched if block.text.strip()]


def _html_to_markdownish(text: str) -> str:
    soup = BeautifulSoup(text, "html.parser")
    for img in soup.find_all("img"):
        alt = img.get("alt", "")
        src = img.get("src", "")
        img.replace_with(f"\n![{alt}]({src})\n")
    for pre in soup.find_all("pre"):
        pre.replace_with(f"\n```\n{pre.get_text()}\n```\n")
    return soup.get_text("\n")


def _parse_text_and_images(text: str, heading: str) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    cursor = 0
    for match in MD_IMAGE_RE.finditer(text):
        blocks.extend(_split_text_blocks(text[cursor : match.start()], heading))
        alt = match.group("alt").strip()
        src = match.group("src").strip()
        image_text = f"Image alt: {alt or 'empty'}\nImage src: {src}"
        blocks.append(ParsedBlock("image", image_text, {"heading": heading, "imageAlt": alt, "imageSrc": src}))
        cursor = match.end()
    blocks.extend(_split_text_blocks(text[cursor:], heading))
    return blocks


def _split_text_blocks(text: str, heading: str) -> list[ParsedBlock]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    return [ParsedBlock("text", paragraph, {"heading": heading}) for paragraph in paragraphs]


def _extract_heading(text: str) -> str | None:
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    match = HEADING_RE.match(first_line)
    return match.group(2).strip() if match else None
