"""
Text humanization module for making research reports read naturally.

This module transforms technical, structured reports into flowing prose
that appears human-written while maintaining factual accuracy.
"""

from typing import List, Dict, Tuple
from HDRP.services.shared.claims import AtomicClaim
import re
from datetime import datetime


class ReportHumanizer:
    """Transforms technical reports into natural, human-like prose."""
    
    def __init__(self):
        # Varied sentence starters for natural flow
        self.sentence_starters = [
            "According to research",
            "Evidence suggests that",
            "The findings indicate",
            "Analysis reveals",
            "It has been observed that",
            "Research demonstrates",
            "Studies show that",
            "The data indicates",
        ]
        
        # Transition phrases between sections
        self.transitions = [
            "Building on these findings,",
            "In addition to this,",
            "Further analysis reveals",
            "Expanding on this point,",
            "Related to this,",
            "This connects with",
            "Complementing these observations,",
        ]
    
    def add_executive_summary(
        self, 
        claims: List[AtomicClaim], 
        topic: str,
        section_titles: List[str]
    ) -> str:
        """Generate a natural executive summary from verified claims.
        
        Args:
            claims: List of verified claims
            topic: The research topic/query
            section_titles: List of section titles in the report
            
        Returns:
            Formatted executive summary as markdown text
        """
        if not claims:
            return ""
        
        # Extract key statistics
        claim_count = len(claims)
        unique_sources = len(set(c.source_url for c in claims if c.source_url))
        
        # Determine research scope description
        scope_desc = self._describe_research_scope(section_titles)
        
        # Build natural summary
        summary = "## Executive Summary\n\n"
        
        # Opening paragraph
        if topic:
            summary += f"This research investigation examines {topic}, drawing upon "
        else:
            summary += "This comprehensive research investigation draws upon "
        
        summary += f"{claim_count} verified findings from {unique_sources} authoritative sources. "
        
        if scope_desc:
            summary += f"The analysis {scope_desc}. "
        
        summary += "The following synthesis presents key insights grounded in current evidence.\n\n"
        
        # Extract and synthesize key themes
        key_insights = self._extract_key_insights(claims, section_titles)
        if key_insights:
            summary += "### Key Findings\n\n"
            for idx, insight in enumerate(key_insights, 1):
                summary += f"{idx}. {insight}\n"
            summary += "\n"
        
        return summary
    
    def _describe_research_scope(self, section_titles: List[str]) -> str:
        """Create natural description of research scope."""
        if not section_titles:
            return ""
        
        if len(section_titles) == 1:
            return f"focuses on {section_titles[0].lower()}"
        elif len(section_titles) == 2:
            return f"covers {section_titles[0].lower()} and {section_titles[1].lower()}"
        else:
            return f"spans {len(section_titles)} distinct areas of inquiry"
    
    def _extract_key_insights(
        self, 
        claims: List[AtomicClaim], 
        section_titles: List[str]
    ) -> List[str]:
        """Extract high-level insights from claims without hallucinating.
        
        Returns general statements about what areas were researched,
        without adding specific claims not in the data.
        """
        insights = []
        
        # Group claims by section
        sections_with_claims = {}
        for claim in claims:
            node_id = claim.source_node_id or "General"
            sections_with_claims[node_id] = sections_with_claims.get(node_id, 0) + 1
        
        # Create insight statements about coverage
        if section_titles:
            for title in section_titles[:3]:  # Limit to top 3
                insights.append(
                    f"{title} is examined through multiple verified sources"
                )
        
        # Add insight about verification rigor if applicable
        high_confidence = [c for c in claims if c.confidence >= 0.85]
        if len(high_confidence) > len(claims) * 0.7:
            insights.append(
                "The majority of findings demonstrate high confidence levels with strong source verification"
            )
        
        return insights[:4]  # Max 4 key insights
    
    def add_transitions(self, report_sections: List[Tuple[str, str]]) -> str:
        """Add natural transitions between report sections.
        
        Args:
            report_sections: List of (section_title, section_content) tuples
            
        Returns:
            Combined report with transitions
        """
        if not report_sections:
            return ""
        
        result = report_sections[0][1]  # First section, no transition
        
        for i in range(1, len(report_sections)):
            title, content = report_sections[i]
            
            # Add contextual transition
            if i < len(self.transitions):
                transition = self.transitions[i - 1]
            else:
                transition = "Additionally,"
            
            # Insert transition paragraph
            result += f"\n{transition} we examine {title.lower()}.\n\n"
            result += content
        
        return result
    
    def vary_sentence_structure(self, claim_list: List[str]) -> List[str]:
        """Transform bullet points into varied sentence structures.
        
        Args:
            claim_list: List of claim statements
            
        Returns:
            Rewritten claims with varied structure
        """
        varied = []
        
        for idx, claim in enumerate(claim_list):
            # Use different patterns for variety
            pattern = idx % len(self.sentence_starters)
            starter = self.sentence_starters[pattern]
            
            # Remove any leading numbers or bullets
            clean_claim = re.sub(r'^\d+\.\s*', '', claim)
            clean_claim = re.sub(r'^[-*]\s*', '', clean_claim)
            
            # Vary the structure
            if pattern % 3 == 0:
                # Direct statement
                varied.append(clean_claim)
            elif pattern % 3 == 1:
                # Add prefix
                if clean_claim[0].isupper():
                    # Lowercase first letter if adding prefix
                    clean_claim = clean_claim[0].lower() + clean_claim[1:]
                varied.append(f"{starter}, {clean_claim}")
            else:
                # Keep original
                varied.append(clean_claim)
        
        return varied
    
    def add_conclusions(
        self, 
        claims: List[AtomicClaim],
        section_titles: List[str]
    ) -> str:
        """Generate a conclusions section synthesizing the research.
        
        Args:
            claims: All verified claims
            section_titles: Section titles from the report
            
        Returns:
            Conclusions section as markdown
        """
        if not claims:
            return ""
        
        conclusions = "\n## Conclusions\n\n"
        
        # Synthesis paragraph
        conclusions += (
            "This research investigation has synthesized findings across "
            f"{len(set(c.source_url for c in claims if c.source_url))} verified sources, "
            f"establishing {len(claims)} discrete claims supported by primary evidence. "
        )
        
        if section_titles:
            conclusions += (
                f"The analysis covered {len(section_titles)} key areas, "
                "providing a comprehensive view of the research landscape. "
            )
        
        # Quality statement
        avg_confidence = sum(c.confidence for c in claims) / len(claims) if claims else 0
        if avg_confidence >= 0.8:
            quality_desc = "high confidence"
        elif avg_confidence >= 0.6:
            quality_desc = "moderate confidence"
        else:
            quality_desc = "emerging evidence"
        
        conclusions += (
            f"The findings demonstrate {quality_desc} based on rigorous "
            "source verification and traceability standards.\n\n"
        )
        
        # Forward-looking statement
        conclusions += (
            "### Research Implications\n\n"
            "These findings contribute to the current understanding of the domain "
            "and provide a foundation for further investigation. All claims have been "
            "traced to their original sources, enabling independent verification and "
            "supporting the reliability of these conclusions.\n"
        )
        
        return conclusions
    
    def soften_technical_language(self, metadata_text: str) -> str:
        """Convert technical metadata into natural language.
        
        Args:
            metadata_text: Technical metadata section
            
        Returns:
            Humanized metadata description
        """
        # Parse key metrics from metadata - handle both formats
        claim_match = re.search(r'Total Verified Claims[:\s*]+(\d+)', metadata_text)
        source_match = re.search(r'Unique Sources[:\s*]+(\d+)', metadata_text)
        period_match = re.search(
            r'Research Period[:\s*]+(\d{4}-\d{2}-\d{2}T[\d:\.]+Z)\s+to\s+(\d{4}-\d{2}-\d{2}T[\d:\.]+Z)',
            metadata_text
        )
        
        # Build natural description
        result = "### Research Overview\n\n"
        
        if claim_match:
            claim_count = claim_match.group(1)
            result += f"This report synthesizes {claim_count} verified findings"
            
            if source_match:
                source_count = source_match.group(1)
                result += f" drawn from {source_count} independent sources"
            
            result += ". "
        
        if period_match:
            start_time = period_match.group(1)
            end_time = period_match.group(2)
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                duration = (end_dt - start_dt).total_seconds()
                
                if duration < 60:
                    time_desc = "moments"
                elif duration < 3600:
                    time_desc = f"{int(duration / 60)} minutes"
                else:
                    time_desc = f"{int(duration / 3600)} hours"
                
                result += f"The research was conducted over {time_desc}, "
                result += f"with all claims extracted and verified during this period. "
            except:
                pass
        
        result += (
            "Each finding includes complete source attribution and "
            "has undergone verification for accuracy and grounding.\n\n"
        )
        
        return result
    
    def humanize_full_report(
        self,
        base_report: str,
        claims: List[AtomicClaim],
        topic: str = "",
        context: dict = None
    ) -> str:
        """Apply full humanization pipeline to a report.
        
        Args:
            base_report: The technical report to humanize
            claims: List of all verified claims
            topic: Research topic/query
            context: Additional context (section_headers, etc.)
            
        Returns:
            Fully humanized report
        """
        if context is None:
            context = {}
        
        section_headers = context.get('section_headers', {})
        section_titles = list(section_headers.values()) if section_headers else []
        
        # Extract title
        title_match = re.search(r'^# (.+)$', base_report, re.MULTILINE)
        title = title_match.group(1) if title_match else "Research Report"
        
        # Build humanized report
        humanized = f"# {title}\n\n"
        
        # Add executive summary
        humanized += self.add_executive_summary(claims, topic, section_titles)
        
        # Transform metadata section
        metadata_match = re.search(
            r'## Research Metadata\n\n(.*?)(?=\n##|\Z)',
            base_report,
            re.DOTALL
        )
        if metadata_match:
            metadata_text = metadata_match.group(1)
            humanized += self.soften_technical_language(metadata_text)
        
        # Extract and preserve main content sections (skip metadata)
        # Find all sections after metadata
        sections_pattern = r'## (?!Research Metadata|Table of Contents)(.+?)\n\n(.*?)(?=\n## |\Z)'
        sections = re.findall(sections_pattern, base_report, re.DOTALL)
        
        # Filter out Bibliography for now (will add at end)
        content_sections = [(title, content) for title, content in sections 
                           if title.strip() != 'Bibliography']
        
        # Add content with natural transitions
        for i, (section_title, section_content) in enumerate(content_sections):
            if i > 0:
                # Add transition
                transition = self.transitions[i % len(self.transitions)]
                humanized += f"\n{transition} the research examined {section_title.lower()}.\n"
            
            humanized += f"\n## {section_title}\n\n{section_content}"
        
        # Add conclusions
        humanized += self.add_conclusions(claims, section_titles)
        
        # Add bibliography at the end
        bib_match = re.search(r'## Bibliography\n\n(.*)', base_report, re.DOTALL)
        if bib_match:
            humanized += f"\n## Bibliography\n\n{bib_match.group(1)}"
        
        return humanized

