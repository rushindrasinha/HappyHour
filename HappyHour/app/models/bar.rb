class Bar < ActiveRecord::Base
  belongs_to :user
  has_many :offers
  mount_uploader :image, ImageUploader
end
