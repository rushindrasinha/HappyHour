class Bar < ActiveRecord::Base
  belongs_to :user
  has_many :offers
  has_attached_file :image, :styles => { :medium => "500x500>", :thumb => "100x100>" }, :default_url => "https://s3-us-west-1.amazonaws.com/happyhour-rushi/Bar.jpg"
  validates_attachment_content_type :image, :content_type => ["image/jpg", "image/jpeg", "image/png"]
end
