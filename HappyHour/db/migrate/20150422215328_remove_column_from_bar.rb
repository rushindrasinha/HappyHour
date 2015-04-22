class RemoveColumnFromBar < ActiveRecord::Migration
  def change
    remove_column :bars, :image, :string
  end
end
