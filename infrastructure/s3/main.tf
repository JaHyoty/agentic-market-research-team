variable "bucket_prefix" {}

resource "aws_s3_bucket" "artifacts" {
  bucket_prefix = "${var.bucket_prefix}-artifacts"
}

resource "aws_s3_bucket" "reports" {
  bucket_prefix = "${var.bucket_prefix}-reports"
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "reports_bucket" {
  value = aws_s3_bucket.reports.bucket
}

output "reports_bucket_arn" {
  value = aws_s3_bucket.reports.arn
}
