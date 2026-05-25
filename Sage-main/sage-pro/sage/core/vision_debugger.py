"""
SAGE-PRO Vision Debugger — "Look at This"
═══════════════════════════════════════════
Feature 2: Multi-modal vision debugging via VLM integration.

When a user pastes a screenshot of a broken UI, plot, or error,
the Vision Debugger:
  1. Encodes the image to base64
  2. Sends it to a Vision Language Model (LLaVA / Qwen-VL / GPT-4o)
  3. Gets a structured analysis of what's visually wrong
  4. Maps the visual defect to the corresponding code region
  5. Returns a targeted fix

This enables the "Look at this bug" workflow where the user
simply screenshots a problem and the IDE fixes it automatically.

The VLM is accessed via the same vLLM/OpenAI-compatible API
that the other agents use, just with a vision-capable model.
"""

import asyncio
import base64
import hashlib
import re
import structlog
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = structlog.get_logger(__name__)


class VisionDebugger:
    """Multi-modal visual debugging via Vision Language Models."""

    def __init__(
        self,
        base_url: str = "http://localhost:8005/v1",
        model_name: str = "llava:34b",
        max_tokens: int = 4096,
    ) -> None:
        """Initializes the Vision Debugger.

        Args:
            base_url: vLLM endpoint serving the vision model.
            model_name: Vision-capable model name.
            max_tokens: Max response tokens.
        """
        self.base_url = base_url
        self.model_name = model_name
        self.max_tokens = max_tokens

        logger.info(
            "vision_debugger_initialized",
            model=model_name,
            endpoint=base_url,
        )

    def encode_image(self, image_path: str) -> str:
        """Encodes an image file to base64 data URI.

        Args:
            image_path: Path to the image file.

        Returns:
            Base64-encoded data URI string.
        """
        path = Path(image_path)
        suffix = path.suffix.lower()

        mime_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp',
        }
        mime_type = mime_map.get(suffix, 'image/png')

        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('utf-8')

        return f"data:{mime_type};base64,{data}"

    def encode_image_bytes(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Encodes raw image bytes to base64 data URI.

        Args:
            image_bytes: Raw image bytes.
            mime_type: MIME type of the image.

        Returns:
            Base64-encoded data URI string.
        """
        data = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:{mime_type};base64,{data}"

    async def analyze_screenshot(
        self,
        image_data_uri: str,
        user_description: str = "",
        relevant_code: str = "",
    ) -> Dict[str, Any]:
        """Analyzes a screenshot with the Vision Language Model.

        Args:
            image_data_uri: Base64-encoded data URI of the screenshot.
            user_description: User's description of the problem (optional).
            relevant_code: The code that generated this visual output.

        Returns:
            Dict with 'analysis', 'defects', 'suggested_fix', and 'confidence'.
        """
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            base_url=self.base_url,
            api_key="not-needed",
        )

        system_prompt = """You are a Visual Debugging Agent in the SAGE-PRO IDE.
Your job is to analyze screenshots of broken UIs, incorrect plots, misaligned layouts,
and visual bugs. You must:

1. IDENTIFY the exact visual defect (misalignment, wrong color, broken layout, etc.)
2. LOCATE which part of the screenshot shows the problem
3. MAP the defect to a likely code cause (CSS property, HTML structure, data error, etc.)
4. SUGGEST a precise, minimal code fix

Output your analysis in this EXACT format:

## Visual Defects Found
- [DEFECT_1]: Description of the visual issue
- [DEFECT_2]: Description (if multiple)

## Root Cause Analysis
The visual defect is caused by: [explanation]

## Code Fix
```[language]
[the fix]
```

## Confidence
[HIGH/MEDIUM/LOW] — [brief justification]
"""

        user_content: List[Dict[str, Any]] = []

        # Add the image
        user_content.append({
            "type": "image_url",
            "image_url": {"url": image_data_uri},
        })

        # Build text prompt
        text_parts = ["Analyze this screenshot for visual bugs and suggest fixes."]
        if user_description:
            text_parts.append(f"\nUser's description: {user_description}")
        if relevant_code:
            text_parts.append(f"\nRelevant code:\n```\n{relevant_code}\n```")

        user_content.append({
            "type": "text",
            "text": "\n".join(text_parts),
        })

        try:
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=self.max_tokens,
                temperature=0.1,
            )

            analysis_text = response.choices[0].message.content or ""

            # Parse structured output
            defects = self._extract_defects(analysis_text)
            code_fix = self._extract_code_fix(analysis_text)
            confidence = self._extract_confidence(analysis_text)

            result = {
                "analysis": analysis_text,
                "defects": defects,
                "suggested_fix": code_fix,
                "confidence": confidence,
                "model": self.model_name,
            }

            logger.info(
                "vision_analysis_complete",
                defects_found=len(defects),
                confidence=confidence,
            )
            return result

        except Exception as e:
            logger.error("vision_analysis_failed", error=str(e))
            return {
                "analysis": f"Vision analysis failed: {str(e)}",
                "defects": [],
                "suggested_fix": None,
                "confidence": "NONE",
                "error": str(e),
            }

    def _extract_defects(self, text: str) -> List[str]:
        """Extracts defect descriptions from the VLM analysis.

        Args:
            text: Raw VLM response.

        Returns:
            List of defect description strings.
        """
        defects = []
        pattern = r'\[DEFECT_\d+\]:\s*(.+)'
        matches = re.findall(pattern, text)
        if matches:
            defects = [m.strip() for m in matches]
        else:
            # Fallback: look for bullet points under "Visual Defects"
            section = re.search(
                r'## Visual Defects.*?\n(.*?)(?=\n## |\Z)',
                text, re.DOTALL
            )
            if section:
                for line in section.group(1).strip().split('\n'):
                    line = line.strip().lstrip('- •')
                    if line:
                        defects.append(line)
        return defects

    def _extract_code_fix(self, text: str) -> Optional[str]:
        """Extracts the code fix from the VLM analysis.

        Args:
            text: Raw VLM response.

        Returns:
            The extracted code fix, or None.
        """
        pattern = r'## Code Fix\s*\n```\w*\n(.*?)```'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None

    def _extract_confidence(self, text: str) -> str:
        """Extracts the confidence level from the VLM analysis.

        Args:
            text: Raw VLM response.

        Returns:
            'HIGH', 'MEDIUM', 'LOW', or 'UNKNOWN'.
        """
        pattern = r'## Confidence\s*\n\s*(HIGH|MEDIUM|LOW)'
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).upper() if match else "UNKNOWN"

    async def debug_with_context(
        self,
        image_data_uri: str,
        user_description: str,
        code_context: Dict[str, str],
        architect_spec: str = "",
    ) -> Dict[str, Any]:
        """Full debugging pipeline: visual analysis + code mapping.

        This is the entry point called by the LangGraph human_feedback_gate
        when the user submits a screenshot.

        Args:
            image_data_uri: Base64 screenshot.
            user_description: What the user says is wrong.
            code_context: Dict of filename → code content.
            architect_spec: The Architect's original spec for reference.

        Returns:
            Complete debug report with analysis, fix, and affected files.
        """
        # Combine all code context
        combined_code = "\n\n".join(
            f"# --- {fname} ---\n{content}"
            for fname, content in code_context.items()
        )

        # Truncate if too long
        if len(combined_code) > 8000:
            combined_code = combined_code[:8000] + "\n... [truncated]"

        analysis = await self.analyze_screenshot(
            image_data_uri=image_data_uri,
            user_description=user_description,
            relevant_code=combined_code,
        )

        # Identify which files are likely affected
        affected_files = []
        if analysis.get("suggested_fix"):
            fix_lower = analysis["suggested_fix"].lower()
            for fname in code_context:
                # Check if the fix references this file's patterns
                fname_base = Path(fname).stem.lower()
                if fname_base in fix_lower or any(
                    keyword in fix_lower
                    for keyword in ['style', 'css', 'margin', 'padding', 'flex']
                    if keyword in code_context[fname].lower()
                ):
                    affected_files.append(fname)

        analysis["affected_files"] = affected_files
        analysis["architect_context"] = bool(architect_spec)

        logger.info(
            "vision_debug_complete",
            defects=len(analysis.get("defects", [])),
            affected_files=affected_files,
        )
        return analysis
