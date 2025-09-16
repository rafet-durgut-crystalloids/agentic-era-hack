terraform {
  backend "gcs" {
    bucket = "qwiklabs-gcp-04-e0479738a642-terraform-state"
    prefix = "agentic-era-hack/prod"
  }
}
