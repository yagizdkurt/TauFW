# Basic coding guidelines

- **Avoid magic numbers.** Give meaningful names to constants and explain units
  and the reason for analysis thresholds. Put campaign settings in configuration.
- **Use clear names.** Names should describe what a variable, function or file
  represents. Follow the surrounding code's conventions.
- **Keep functions focused.** Give each function one clear responsibility and
  avoid unnecessary complexity.
- **Avoid duplicated code.** Reuse existing helpers before adding another copy.
- **Make inputs explicit.** Avoid hardcoded personal paths; accept paths and
  campaign options through arguments or configuration.
- **Handle errors clearly.** Validate required inputs and report useful errors.
  Do not silently hide failures.
- **Explain why.** Comment assumptions, physics choices and unusual behavior
  rather than restating the code.
- **Keep changes focused.** Check the behavior you changed with a small relevant
  validation, review your diff, and update affected documentation.
