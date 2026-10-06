Fix the typo on the sign-in page.

<!-- spec:start version=1 -->
Path: quick

## Goal
The sign-in page says "Password", not "Pasword".

## Expected flow
FL-1 The user opens the sign-in page and reads the label.

## Edge cases
EC-1 When the page loads in French, then the label says "Mot de passe".

## Must stay the same
Sign-in still works (tests/signin.test.ts).

## Judge
Kind: single test
Command: npm test -- tests/signin-label.test.ts
Proves: FL-1, EC-1

## Links
Touches: sign-in
<!-- spec:end -->
