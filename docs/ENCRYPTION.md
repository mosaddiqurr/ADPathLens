# Encryption

Sensitive profile values and secret variables use AES-256-GCM. Each ciphertext contains a key
identifier, nonce, ciphertext, and authentication tag. The key ring contains one active key and
optional previous keys for rotation.

Profile associated data is:

```text
test_session:{project_id}:{target_id}:{profile_id}:{field}
```

Moving ciphertext to a different project, target, profile, or field therefore fails
authentication. The API maps authentication or decoding failures to a generic safe error and
never returns plaintext.

Credential fingerprints use HMAC-SHA-256 with a key derived from the active encryption key via
HKDF. They help operators distinguish versions without enabling offline comparison against a raw
unkeyed digest.

Secrets exist transiently in process memory during authorized replay. Python does not guarantee
complete memory zeroization, so the design limits lifetime and serialization rather than claiming
perfect erasure. Keys belong in a platform secret store or protected environment injection in
production. `.env`, runtime secret files, databases, and reports are excluded from source archives.
