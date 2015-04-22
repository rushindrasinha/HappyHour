class RemoveColumnFromOffer < ActiveRecord::Migration
  def change
    remove_column :offers, :image, :string
  end
end
