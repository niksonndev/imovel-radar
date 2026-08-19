resource "aws_s3_bucket" "artifacts" {
  bucket = var.artifact_bucket
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# Upload do zip feito pelo próprio Terraform (o CI passa o zip_path).
resource "aws_s3_object" "scraper_artifact" {
  bucket = aws_s3_bucket.artifacts.id
  key    = var.artifact_key
  source = var.zip_path
  etag   = filemd5(var.zip_path)
}
