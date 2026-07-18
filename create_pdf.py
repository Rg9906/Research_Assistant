"""Manual dev script: generates a synthetic test PDF at data/papers/paper1.pdf.

Not part of the pytest suite — used for ad-hoc smoke-testing the paper_chat
session/indexing pipeline against a real (if synthetic) PDF on disk.
"""

import fitz

text_content = """Testora: Using Natural Language Intent to
Detect Behavioral Regressions
Michael Pradel
michael@binaervarianz.de
CISPA Helmholtz Center for Information Security
Stuttgart, Germany

1 Introduction
Practically all successful software projects are continuously evolving. While changing code is necessary to fix bugs, add new features,
improve performance, or increase the maintainability of a code
base, code changes may also negatively impact the software. For
example, while trying to fix a specific bug, a developer may not
only remove the buggy behavior, but also accidentally introduce
a new bug or modify the behavior in some other unintended way.
Prior work shows that behavioral changes are common in practice,
leading to regression bugs that often remain unnoticed [41].

As a real-world example of a regression bug, consider Figure 1,
which shows a pull request (PR) of the popular Python scipy library. The title and description of the PR indicate that the change
is intended to add array API support to the differential_entropy
function. Adding array API support is a larger design change in
scipy, which affects how the library internally handles different
array types, but it should not change the fundamental behavior of
the mathematical functions offered by scipy. However, as exposed
by the test case in Figure 1, the output of the differential_entropy
function changes from 2.3588 to 2.5285 after the PR is applied. That
is, the PR causes an unintended behavioral difference, as the output of the function should not change for the same input data just
because the internal handling of arrays changes. The regression
remained unnoticed by the developers, who merged the PR into
the code base without realizing the unintended behavioral change.

As illustrated by this example, regressions may easily remain
unnoticed. One reason is that, even in well tested software, the
available test suite may not cover the code modified by a code
change. Automated regression test generation [5, 18, 46, 50, 55] can
partially address this challenge, but lacks a useful test oracle: If a
regression test generator finds a test that exposes a behavioral difference between the code before and after a code change, it remains
unclear whether this behavioral difference is intended. A naive approach could report any behavioral difference as a regression, but
this would lead to many false positives, because most code changes
are supposed to change the behavior in some way, e.g., to fix a bug
or to add a new feature [5, 41].

This paper presents Testora, an automated technique to detect
regressions and other unintended behavioral changes by using
natural language information associated with a code change as a
test oracle. Our key idea is to compare the intentions of a code
change, as provided informally in natural language, with behavioral changes exposed by generated regression tests. The approach
checks PRs for unintended behavioral changes by performing three
steps: (1) At first, given the code diff associated with the PR, Testora
performs a targeted test generation aimed at finding tests that expose behavioral differences between the original and the modified
code.
"""

doc = fitz.open()
page = doc.new_page()
# insert text
page.insert_text(fitz.Point(50, 50), text_content, fontsize=11)

doc.save("data/papers/paper1.pdf")
doc.close()
print("PDF created at data/papers/paper1.pdf")
