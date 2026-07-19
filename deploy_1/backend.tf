terraform {
  backend "s3" {
    bucket         = "spendsense-tfstate-359615771071"
    key            = "spendsense/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "spendsense-tfstate-lock"
    encrypt        = true
  }
}