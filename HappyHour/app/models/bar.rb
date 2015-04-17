class Bar < ActiveRecord::Base
  belongs_to :user
  has_many :offers
end
