"""
Patch Hermes agent/system_prompt.py for LAAP integration

This script modifies Hermes' agent/system_prompt.py to inject LAAP cognitive state
into the volatile system prompt tier during system prompt construction.

Usage:
    python patch_hermes_system_prompt.py <hermes_home>

Where <hermes_home> is the Hermes installation directory (e.g., ~/.hermes/hermes-agent)
"""

import os
import sys
import shutil
import requests
from pathlib import Path

LAAP_API_BASE = os.environ.get("LAAP_API_BASE", "http://localhost:11546")


def get_lap_cognitive_state(user_input: str) -> dict:
    """Call LAAP /v1/cognitive_state endpoint to get PSI state."""
    try:
        resp = requests.post(
            f"{LAAP_API_BASE}/v1/cognitive_state",
            json={"input": user_input},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"[LAAP Integration] Failed to get cognitive state: {e}")
        return None


def patch_system_prompt(hermes_home: str):
    """Patch Hermes agent/system_prompt.py for LAAP integration."""
    system_prompt_path = Path(hermes_home) / "agent" / "system_prompt.py"
    backup_path = Path(hermes_home) / "agent" / "system_prompt.py.laap-backup"

    if not system_prompt_path.exists():
        print(f"Error: {system_prompt_path} not found!")
        print(f"Please ensure {hermes_home} is the correct Hermes installation directory.")
        sys.exit(1)

    # Create backup
    print(f"Creating backup: {backup_path}")
    shutil.copy2(system_prompt_path, backup_path)

    # Read original file
    with open(system_prompt_path, 'r', encoding='utf-8') as f:
        original_content = f.read()

    # Check if already patched
    if "LAAP_COGNITIVE_STATE_INJECTION" in original_content:
        print("LAAP integration already applied to system_prompt.py")
        return

    # Define the LAAP injection code
    laap_injection_code = '''
# ════════════════════════════════════════════════════════
# LAAP_COGNITIVE_STATE_INJECTION
# Inject LAAP cognitive state into volatile system prompt tier
# ════════════════════════════════════════════════════════

def _get_laap_cognitive_preamble(user_input: str = "") -> str:
    """
    Fetch LAAP cognitive state preamble to inject into volatile system prompt.
    
    This does not break prompt caching because it only affects the volatile tier.
    """
    laap_api_base = os.environ.get("LAAP_API_BASE", "__LAAP_API_BASE__")
    
    try:
        resp = requests.post(
            f"{laap_api_base}/v1/cognitive_state",
            json={"input": user_input},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            preamble = data.get("preamble", "")
            cot_hint = data.get("cot_hint", "")
            
            if preamble or cot_hint:
                parts = []
                if preamble:
                    parts.append(f"[LAAP COGNITIVE STATE]\\n{preamble}")
                if cot_hint:
                    parts.append(f"[LAAP CO-T HINT]\\n{cot_hint}")
                return "\\n\\n".join(parts)
    except Exception as e:
        pass
    
    return ""


def _inject_laap_state_into_volatile(volatile_tier: list, user_input: str = ""):
    """
    Inject LAAP cognitive preamble into the volatile system prompt tier.
    """
    preamble = _get_laap_cognitive_preamble(user_input)
    if preamble:
        # Insert at the beginning of volatile tier
        volatile_tier.insert(0, {
            "type": "text",
            "content": preamble,
            "weight": 0.5,
        })
'''

    # Find the location to inject the code (after imports and before main functions)
    # Look for a good insertion point, typically after imports and class definitions
    
    # Insert the LAAP injection code before the main system prompt building function
    injection_marker = "# LAAP_COGNITIVE_STATE_INJECTION"
    
    # Find a good insertion point - after imports and before class definitions or main functions
    lines = original_content.split('\n')
    insert_index = 0
    
    # Find the end of imports section
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            insert_index = i + 1
        elif line.startswith('class ') or ('def build_system_prompt' in line or 'def get_system_prompt' in line):
            # Insert before class or main function definitions
            insert_index = i
            break
    
    # Insert the LAAP code
    laap_code_lines = laap_injection_code.replace('__LAAP_API_BASE__', LAAP_API_BASE).split('\n')
    for i, line in enumerate(laap_code_lines):
        lines.insert(insert_index + i, line)
    
    # Add the injection call to the system prompt building function
    # Look for the volatile tier construction or system prompt assembly
    
    modified_content = '\n'.join(lines)
    
    # Add the injection call before volatile_parts is built or returned
    # Find a pattern like "volatile_parts =" or "volatile_parts.append(timestamp_line)"
    injection_call = '''
    # Inject LAAP cognitive state into volatile_parts if user input is available
    if hasattr(agent, 'user_input') and agent.user_input:
        laap_preamble = _get_laap_cognitive_preamble(agent.user_input)
        if laap_preamble:
            volatile_parts.insert(0, laap_preamble)
    elif hasattr(agent, 'last_user_message') and agent.last_user_message:
        laap_preamble = _get_laap_cognitive_preamble(agent.last_user_message)
        if laap_preamble:
            volatile_parts.insert(0, laap_preamble)
'''

    # Try to find where volatile_parts is being built or returned
    if 'volatile_parts' in modified_content:
        # Insert injection call before volatile_parts.append(timestamp_line)
        patterns_to_find = [
            "volatile_parts.append(timestamp_line)",
            'volatile_parts.append(timestamp_line)',
        ]
        
        for pattern in patterns_to_find:
            if pattern in modified_content:
                # Find the line with this pattern
                lines_modified = modified_content.split('\n')
                for i, line in enumerate(lines_modified):
                    if pattern in line and not line.strip().startswith('#'):
                        # Insert the injection call before this line
                        lines_modified.insert(i, injection_call.rstrip())
                        modified_content = '\n'.join(lines_modified)
                        break
                break
    
    # Write modified content
    with open(system_prompt_path, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    print(f"LAAP integration patched into: {system_prompt_path}")
    print(f"Backup saved to: {backup_path}")
    print(f"LAAP API Base: {LAAP_API_BASE}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python patch_hermes_system_prompt.py <hermes_home>")
        print("Example: python patch_hermes_system_prompt.py ~/.hermes/hermes-agent")
        sys.exit(1)
    
    hermes_home = sys.argv[1]
    patch_system_prompt(hermes_home)


if __name__ == "__main__":
    main()
