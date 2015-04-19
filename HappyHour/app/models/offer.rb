class Offer < ActiveRecord::Base
  belongs_to :bar
  mount_uploader :image, ImageUploader
end
