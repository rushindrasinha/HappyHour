# encoding: utf-8

class ImageUploader < CarrierWave::Uploader::Base

  # Include RMagick or MiniMagick support:
  include CarrierWave::RMagick
  #include CarrierWave::MiniMagick
  include CarrierWave::MiniMagick

  process resize_to_fit: [400, 400]

  #
  # CarrierWave.configure do |config|
  #   config.storage    = :aws
  #   config.aws_bucket = ENV.fetch('happyhour-rushi')
  #   config.aws_acl    = :public_read
  #   config.asset_host = 'http://happyhour-rushi.herokuapp.com'
  #   config.aws_authenticated_url_expiration = 60 * 60 * 24 * 365
  #
  #   config.aws_credentials = {
  #     access_key_id:     ENV.fetch('AWS_ACCESS_KEY_ID'),
  #     secret_access_key: ENV.fetch('AWS_SECRET_ACCESS_KEY')
  #   }
  #   end


  # Choose what kind of storage to use for this uploader:
  storage :file
  # storage :fog

  # Override the directory where uploaded files will be stored.
  # This is a sensible default for uploaders that are meant to be mounted:
  def store_dir
    "uploads/#{model.class.to_s.underscore}/#{mounted_as}/#{model.id}"
  end

  # Provide a default URL as a default if there hasn't been a file uploaded:
  # def default_url
  #   # For Rails 3.1+ asset pipeline compatibility:
  #   # ActionController::Base.helpers.asset_path("fallback/" + [version_name, "default.png"].compact.join('_'))
  #
  #   "/images/fallback/" + [version_name, "default.png"].compact.join('_')
  # end


  # Process files as they are uploaded:
  # process :scale => [200, 300]
  #
  # def scale(width, height)
  #   # do something
  # end

  # Create different versions of your uploaded files:
  version :thumb do
    process :resize_to_fit => [100, 100]
  end

  # Add a white list of extensions which are allowed to be uploaded.
  # For images you might use something like this:
  # def extension_white_list
  #   %w(jpg jpeg gif png)
  # end

  # Override the filename of the uploaded files:
  # Avoid using model.id or version_name here, see uploader/store.rb for details.
  # def filename
  #   "something.jpg" if original_filename
  # end

end
