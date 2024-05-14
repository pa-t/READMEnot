import json
import os
from typing import Dict, List
from openai import OpenAI

client = OpenAI(api_key=input("Enter OpenAI API Key: "))

# PROMPTS
FILE_IDENTIFICATION_SYSTEM_PROMPT = """# Task
You will be given a list of files in a code repository. Extract out a list of files that you would use the contents to write the different parts of a README (Project Title, Description, Installation, Usage, Configuration) for a code repository.

# Additional Info
For project title and description, look at the main files and any UI files that may hold information about what the project is.

Usage information should include any docker or other package manager instructions to build the project.

# Output
Your output will be a JSON object written in the following format. Do not write anything other than this JSON object
```json
{
    "project_title": ["list", "of", "files"],
    "project_description": ["list", "of", "other", "files"],
    "installation": ["list", "of", "files"],
    "usage": ["another", "list", "of", "files"],
    "configuration": ["list", "of", "files"],
}

# CRITICAL INFORMATION
You must ENSURE that the correct paths are retained. Do not confuse any paths or else downstream tasks will fail.
```"""

SECTION_WRITING_SYSTEM_PROMPT = """# Task
You are an expert README writer. Your writing can be found in the best Open Source projects. For the given section of a README and the provided files, write the section as best as you can.

# Output
Just output the section, do not write anything else. Do NOT (!) write anything other than the specified section to write. DO NOT write other sections of a README.

For example, for the project title you would just write "<Project Title>", no markdown formatting or other text is necessary.
For the description section, you would not include information on installation, usage or configuration.
For the installation section, you would not include information on usage or configuration.
For the usage section, this section would be specific to how the user could use the project.
For the configuration section, you would just write about what the user needs to configure to run the project successfully (environment variables and .env files to create).
"""

FORMAT_SYSTEM_PROMPT = """# Task
With the provided information about a code repository, format the text into a README file with the following sections.

```markdown
# {title}

## Description
{description}

## Installation
{installation}

## Usage
{usage}

## Configuration
{configuration}
```

Do not (!) write anything about the repo that you do not know for certain. Some of the sections may have oddities from the extraction portion of this pipeline, feel free to make slight corrections such as removing template text.

Write your output exactly as above. Do not write anything besides this output markdown
"""

DIRS_TO_IGNORE = ['.git', 'venv']
FILES_TO_IGNORE = ['.DS_Store']

# helper functions
def list_files(directory: str) -> List[str]:
    """List all files in the directory and subdirectories, excluding anything under the .git/ directory."""
    if directory == ".":
        directory = os.getcwd()
    else:
        directory = os.path.abspath(directory)
    
    file_list = []
    for root, dirs, files in os.walk(directory):
        # Exclude the .git directory
        dirs[:] = [d for d in dirs if d not in DIRS_TO_IGNORE]
        
        for file in files:
            if file not in FILES_TO_IGNORE:
                file_list.append(os.path.join(root, file))
    return file_list


# OpenAI functions
def decide_interesting_files(file_list: List[str]) -> Dict:
    """Use GPT to decide which files are interesting for different parts of the README."""
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "system", "content": FILE_IDENTIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": f"{file_list}"}
        ],
        max_tokens=500
    )
    output = response.choices[0].message.content.strip()
    output = output.replace("```json", "").replace("```", "")
    return json.loads(output)


def generate_readme_section(section: str, file_list: List[str]) -> str:
    """Use GPT to write section of README"""
    file_context = f"# Section to Write\n{section}\n\n"
    for file in file_list:
        with open(file, 'r') as f:
            file_context += f"## File name: {file}\nContent:\n{f.read()}\n\n"
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "system", "content": SECTION_WRITING_SYSTEM_PROMPT},
            {"role": "user", "content": file_context}
        ],
        max_tokens=500
    )
    return response.choices[0].message.content.strip()


def format_extracted_information(extracted_info: Dict) -> str:
    """Format different sections into one text output"""
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "system", "content": FORMAT_SYSTEM_PROMPT},
            {"role": "user", "content": f"{extracted_info}"}
        ],
        max_tokens=2000
    )
    return response.choices[0].message.content.strip()


def main():
    desired_path = input("Enter path to repo: ")
    files_at_path = list_files(desired_path)
    if files_at_path:
        file_list = decide_interesting_files(files_at_path)
        output_sections = {}
        for section, section_files in file_list.items():
            output_sections[section] = generate_readme_section(section, section_files)
        output_readme = format_extracted_information(output_sections)
        output_file_path = os.path.join(desired_path, "GENERATED_README.md")
        
        # Write the output to the file
        with open(output_file_path, "w") as output_file:
            output_file.write(output_readme)
        
        print(f"wrote readme to {output_file_path}")
    else:
        print("didn't find any files")


if __name__ == "__main__":
    main()