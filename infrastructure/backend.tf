# Partial backend configuration: bucket/key/region are supplied at init time
# (see .github/workflows/deploy.yml) so nothing account-specific lives in the repo.
terraform {
  backend "s3" {
    use_lockfile = true
    encrypt      = true
  }
}
