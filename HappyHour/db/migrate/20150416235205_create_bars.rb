class CreateBars < ActiveRecord::Migration
  def change
    create_table :bars do |t|
      t.string :bar_name
      t.string :location
      t.integer :zip
      t.string :day
      t.references :user, index: true

      t.timestamps null: false
    end
    add_foreign_key :bars, :users
  end
end
