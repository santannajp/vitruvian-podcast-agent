import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=long"],
    cwd=r"c:\Users\jonps\Documents\projetos wesearch\Vitruvian Audio Agent",
    capture_output=True,
    text=True
)
output = result.stdout + "\n" + result.stderr
with open(r"c:\Users\jonps\Documents\projetos wesearch\Vitruvian Audio Agent\test_results.txt", "w", encoding="utf-8") as f:
    f.write(output)
print("Done. Exit code:", result.returncode)
